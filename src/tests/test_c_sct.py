"""C11 contracts, compiler behavior comparisons and language selection."""
from dataclasses import asdict
import importlib
import importlib.util
import json
import os
from pathlib import Path
import pickle
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC))
from operators import create_strategy, get_registry, REGISTRY
from operators.base.language import make_parser
from c_sct_cases import CASES, REJECTIONS, EXTENDED

HAS_C = importlib.util.find_spec("tree_sitter_c") is not None
GCC = shutil.which("gcc")


@unittest.skipUnless(HAS_C, "tree_sitter_c not installed; C validation unavailable")
class CStrategyTests(unittest.TestCase):
    def test_all_forty_have_changed_and_rejected_examples(self):
        self.assertEqual(set(get_registry("c")), set(CASES))
        self.assertEqual(set(CASES), set(REJECTIONS))
        for sid, code in CASES.items():
            with self.subTest(sid=sid):
                op = create_strategy(sid, language="c")
                result = op.apply(code)
                self.assertEqual(result.successful, 1, result)
                self.assertEqual(result.language, "c")
                self.assertNotEqual(code, result.code)
                self.assertFalse(
                    op.parser.parse(result.code.encode()).root_node.has_error
                )
                self.assertEqual(op(code), result.code)
                rejected = op.apply(REJECTIONS[sid])
                self.assertEqual(rejected.successful, 0, rejected)
                self.assertEqual(rejected.code, REJECTIONS[sid])
                self.assertTrue(rejected.rejections)

    def test_c_files_follow_all_table_cells(self):
        from operators import TABLE, LOCATIONS

        for sid, cls in get_registry("c").items():
            location = LOCATIONS[sid]
            prefix = (
                f"operators.c.{location.level}.{location.target}.{location.category}."
            )
            self.assertTrue(cls.__module__.startswith(prefix), cls)
            self.assertIs(
                getattr(importlib.import_module(cls.__module__), cls.__name__), cls
            )
        for language in ("java", "c"):
            count = 0
            for level, targets in TABLE.items():
                for target, categories in targets.items():
                    for category, ids in categories.items():
                        directory = (
                            SRC / "operators" / language / level / target / category
                        )
                        self.assertEqual(directory.is_dir(), bool(ids))
                        files = [
                            p for p in directory.glob("*.py") if p.name != "__init__.py"
                        ]
                        self.assertEqual(len(files), len(ids))
                        count += len(files)
            self.assertEqual(count, 51)

    def test_repeat_seed_utf8_and_global_random(self):
        state = random.getstate()
        for sid, code in CASES.items():
            with self.subTest(sid=sid):
                source = "/* 中文源码 */ " + code
                a = create_strategy(sid, language="c", seed=7).apply(source, 3)
                b = create_strategy(sid, language="c", seed=7).apply(source, 3)
                self.assertEqual(a, b)
                self.assertLessEqual(a.successful, 3)
                self.assertTrue(a.code.startswith("/* 中文源码 */"))
                current = source.encode()
                for change in a.changes:
                    for edit in reversed(change["edits"]):
                        start, end = edit["start_byte"], edit["end_byte"]
                        self.assertEqual(current[start:end].decode(), edit["before"])
                        current = (
                            current[:start] + edit["after"].encode() + current[end:]
                        )
                self.assertEqual(current.decode(), a.code)
        self.assertEqual(state, random.getstate())

    def test_macros_unknown_headers_and_invalid_inputs_rejected(self):
        for sid, code in CASES.items():
            for prefix in (
                "#define a sneaky\n",
                "#include <stdio.h>\n",
                "#if SOMETHING\n#endif\n",
            ):
                result = create_strategy(sid, language="c").apply(prefix + code)
                self.assertEqual(result.successful, 0, (sid, result))
                self.assertIn(
                    "unresolved_preprocessor_context",
                    [r["reason"] for r in result.rejections],
                )
            self.assertEqual(create_strategy(sid, language="c")("int f( {"), "int f( {")
            for k in (-1, True, 0.5):
                with self.assertRaises(ValueError):
                    create_strategy(sid, language="c").apply(code, k)

    def test_extensions_and_partial_parses_are_rejected(self):
        extensions = (
            "int f(int a){return ({int x=a;x;});}",
            'int f(int a){__asm__("" : "+r"(a));return a;}',
            "int f(int a){int g(int x){return x;}return g(a);}",
        )
        for sid in ("WI1", "SD2", "CL1"):
            for code in extensions:
                result = create_strategy(sid, language="c").apply(code)
                self.assertEqual(result.successful, 0, result)
                self.assertIn(
                    "unsupported_c_extension", [r["reason"] for r in result.rejections]
                )
            for code in (
                "int f(int a){",
                "int f(void){int",
                "int f( {",
                "int f(void){for(int i=;",
            ):
                result = create_strategy(sid, language="c").apply(code)
                self.assertEqual(result.successful, 0, result)
                self.assertEqual(result.rejections[0]["reason"], "input_parse_error")

    def test_integer_type_and_scope_boundaries(self):
        examples = [
            ("SE1", "int f(int a){return a/2;}"),
            ("SE2", "int f(int a){a=2;return 1;}"),
            ("SE4", "int f(unsigned a,int b){return a<b;}"),
            ("SE5", "int f(int a){int *p=&a;a++;return *p;}"),
            ("SE6", "int f(volatile int a){a+=1;return a;}"),
            ("SD3", "int f(int a){int x=a+1;return a;}"),
            ("SD1", "int f(int a){int b=2;{int x=b;int b=1;a+=x+b;}return a;}"),
            ("SS5", "int f(int a){int t=a+1;a=(a<2)&&t;return a;}"),
            (
                "CL3",
                "int f(int a){for(int i=0;i<2;i++){int i=1;if(a)continue;a+=i;}return a;}",
            ),
        ]
        for sid, code in examples:
            result = create_strategy(sid, language="c").apply(code)
            self.assertEqual(result.successful, 0, (sid, result))
        for code in (
            "int f(void){return 32768;}",
            "int f(void){return 1U;}",
            "int f(void){return 1L;}",
            "int f(void){return 0xff;}",
        ):
            for sid in ("WC1", "WC3", "WC5"):
                self.assertEqual(create_strategy(sid, language="c")(code), code)
        with self.assertRaises(TypeError):
            create_strategy("SE1", language="c")(b"int f(void){return 1;}")

    def test_redundancy_roundtrip_and_shared_module_paths(self):
        code = "int f(int a){return a;}"
        for insertion, removal in (
            ("SD2", "SD3"),
            ("SS2", "SS3"),
            ("CC2", "CC3"),
            ("CL1", "CL2"),
        ):
            modified = create_strategy(insertion, language="c")(code)
            result = create_strategy(removal, language="c").apply(modified)
            self.assertEqual(result.successful, 1, (insertion, removal, result))
        import operators.tools.source as source
        import operators.base.strategy as strategy

        self.assertEqual(source.__name__, "operators.tools.source")
        self.assertEqual(strategy.__name__, "operators.base.strategy")

    def test_callback_prototype_scope_and_parenthesized_address(self):
        code = "int a=2; int f(int (*callback)(int a)){return a;}"
        self.assertEqual(create_strategy("WI1", language="c")(code), code)
        code = "int f(int a){int *p=&(a);a++;return *p;}"
        self.assertEqual(create_strategy("SE5", language="c")(code), code)
        code = "int a=2;int f(void){int g(int a);return a;}"
        self.assertEqual(create_strategy("WI1", language="c")(code), code)

    def test_name_provider_and_capture(self):
        code = "int f(int a){return a;}"
        result = create_strategy("WI1", language="c", name_provider=lambda _: "count")(
            code
        )
        self.assertIn("int count", result)
        for name in ("int", "_Reserved", "f", "0bad", "a"):
            self.assertEqual(
                create_strategy("WI1", language="c", name_provider=lambda _, n=name: n)(
                    code
                ),
                code,
            )

    def test_language_selection_and_default_java(self):
        from sct_cases import CASES as JAVA_CASES

        for sid, code in JAVA_CASES.items():
            a = create_strategy(sid).apply(code)
            b = create_strategy(sid, language="java").apply(code)
            self.assertEqual(a, b)
            self.assertEqual(a.language, "java")
            old = REGISTRY[sid].__module__.replace("operators.java.", "operators.")
            self.assertIs(
                getattr(importlib.import_module(old), REGISTRY[sid].__name__),
                REGISTRY[sid],
            )
        with self.assertRaises(ValueError):
            create_strategy("SE1", language="cpp")
        self.assertEqual(len(get_registry("java")), 51)
        self.assertEqual(len(get_registry("c")), 51)

    def test_missing_c_dependency_is_isolated(self):
        code = """import builtins
from operators import create_strategy
original = builtins.__import__
def blocked(name, *args, **kwargs):
    if name == 'tree_sitter_c':
        raise ModuleNotFoundError(name)
    return original(name, *args, **kwargs)
builtins.__import__ = blocked
create_strategy('SE1')
try:
    create_strategy('SE1', language='c')
except RuntimeError as exc:
    assert 'tree_sitter_c' in str(exc)
else:
    raise AssertionError('C dependency was not checked')
"""
        subprocess.run(
            [sys.executable, "-c", code], cwd=SRC, check=True, capture_output=True
        )

    def test_c_dependency_does_not_load_in_java_only_process(self):
        code = 'from operators import create_strategy; import sys; create_strategy("SE1"); assert "tree_sitter_c" not in sys.modules'
        subprocess.run(
            [sys.executable, "-c", code], cwd=SRC, check=True, capture_output=True
        )


@unittest.skipUnless(
    HAS_C and GCC, "C grammar or GCC unavailable; behavior validation skipped"
)
class CBehaviorTests(unittest.TestCase):
    harness = '\n#include <stdio.h>\n#include <stdlib.h>\nint main(int argc,char **argv){int a=argc>1?atoi(argv[1]):0;printf("%d\\n",f(a));return 0;}\n'

    def compile(self, directory, stem, code, optimization):
        source = Path(directory) / (stem + ".c")
        binary = Path(directory) / stem
        source.write_text(code + self.harness, encoding="utf-8")
        command = [
            GCC,
            "-std=c11",
            "-pedantic-errors",
            "-Wall",
            optimization,
            "-fsanitize=undefined",
            "-fno-sanitize-recover=all",
            str(source),
            "-o",
            str(binary),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr + "\n" + code)
        return binary

    def run_binary(self, binary, value):
        result = subprocess.run(
            [str(binary), str(value)], capture_output=True, text=True, timeout=2
        )
        self.assertNotIn("runtime error:", result.stderr)
        return result.returncode, result.stdout, result.stderr

    def test_all_forty_and_extended_behavior(self):
        for index, (sid, source) in enumerate(list(CASES.items()) + EXTENDED):
            for k in (1, 3):
                with self.subTest(sid=sid, index=index, k=k):
                    result = create_strategy(
                        sid, language="c", selection="first"
                    ).apply(source, k)
                    self.assertGreater(result.successful, 0, result)
                    with tempfile.TemporaryDirectory() as directory:
                        before = self.compile(directory, "before", source, "-O0")
                        after = self.compile(directory, "after", result.code, "-O2")
                        for value in (-3, -1, 0, 1, 2, 4):
                            self.assertEqual(
                                self.run_binary(before, value),
                                self.run_binary(after, value),
                                result,
                            )

    def test_nontermination_and_condition_side_effect_counts(self):
        for sid, source in [
            ("CL3", "int f(int a){for(;;){continue;}return a;}"),
            ("CL5", "int f(int a){for(;;){continue;}return a;}"),
            ("CL6", "int f(int a){do{continue;}while(1);return a;}"),
            ("CL7", "int f(int a){do{continue;}while(1);return a;}"),
            ("CL8", "int f(int a){while(1){continue;}return a;}"),
        ]:
            result = create_strategy(sid, language="c").apply(source)
            self.assertEqual(result.successful, 1, result)
            with tempfile.TemporaryDirectory() as directory:
                for stem, code in [("before", source), ("after", result.code)]:
                    binary = self.compile(directory, stem, code, "-O0")
                    with self.assertRaises(subprocess.TimeoutExpired):
                        subprocess.run([str(binary)], capture_output=True, timeout=0.15)


@unittest.skipUnless(HAS_C, "C grammar unavailable")
class CEntrypointTests(unittest.TestCase):
    def test_all_cli_help_paths_select_language_without_data_access(self):
        names = ("operate_source", "operate_sct", "operate_astnn_custom", "operate_astnn_combination", "operate_dsfm", "operate_dsfm_custom", "operate_dsfm_combination", "audit_sct_applicability")
        for name in names:
            result = subprocess.run([sys.executable, str(SRC / (name + ".py")), "--help"], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, (name, result.stderr))
            self.assertIn("--language", result.stdout)

    def test_single_source_combinations_log_and_no_overwrite(self):
        from operate_source import main

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.c"
            out = root / "out_c_SE2k1_SD2k1.c"
            source.write_text(CASES["SE2"])
            args = [
                "--language",
                "c",
                "--input",
                str(source),
                "--output",
                str(out),
                "--strategies",
                "SE2:1,SD2:1",
            ]
            main(args)
            records = [
                json.loads(s)
                for s in out.with_name(out.name + ".applications.jsonl")
                .read_text()
                .splitlines()
            ]
            self.assertEqual(records[0]["configuration"]["language"], "c")
            self.assertEqual([r["successful"] for r in records[1:-1]], [1, 1])
            original = out.read_bytes()
            with self.assertRaises(SystemExit):
                main(args)
            self.assertEqual(out.read_bytes(), original)

    def test_source_defaults_to_java_and_c_names_identify_language(self):
        import contextlib
        import io
        from operate_source import main

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.java"
            source.write_text("boolean f(boolean a){return a;}")
            output = root / "output.java"
            main(
                ["--input", str(source), "--output", str(output), "--strategies", "WI1"]
            )
            configuration = json.loads(
                output.with_name(output.name + ".applications.jsonl")
                .read_text()
                .splitlines()[0]
            )
            self.assertEqual(configuration["configuration"]["language"], "java")
            self.assertIn("boolean", output.read_text())
            bad = root / "output.c"
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(
                SystemExit
            ):
                main(
                    [
                        "--language",
                        "c",
                        "--input",
                        str(source),
                        "--output",
                        str(bad),
                        "--strategies",
                        "SE2",
                    ]
                )
            self.assertFalse(bad.exists())

    def test_c_astnn_dsfm_and_audit(self):
        import pandas as pd
        from operate_sct import main
        from audit_sct_applicability import audit

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.tsv"
            pairs = root / "pairs.pkl"
            out = root / "data_c_SE2k1.tsv"
            pd.DataFrame([[0, CASES["SE2"]], [1, CASES["SE2"]]]).to_csv(
                source, sep="\t", header=False, index=False
            )
            pd.DataFrame({"id1": [0], "id2": [0]}).to_pickle(pairs)
            main(
                [
                    "--format",
                    "astnn",
                    "--language",
                    "c",
                    "--input",
                    str(source),
                    "--pairs",
                    str(pairs),
                    "--output",
                    str(out),
                    "--strategies",
                    "SE2",
                ]
            )
            rows = pd.read_csv(out, sep="\t", header=None)
            self.assertNotEqual(rows.iloc[0, 1], CASES["SE2"])
            self.assertEqual(rows.iloc[1, 1], CASES["SE2"])
            report = audit(source, 2, ["SE2"], language="c")
            self.assertEqual(report["language"], "c")
            self.assertEqual(report["strategies"]["SE2"]["new_c_parse_failures"], [])
            ds = root / "ds"
            ds.mkdir()
            dp = root / "dp.pkl"
            dout = root / "ds_c_SE2k1"
            with (ds / "codes.pkl").open("wb") as f:
                pickle.dump(CASES["SE2"], f)
                pickle.dump(CASES["SE2"], f)
            with dp.open("wb") as f:
                pickle.dump(((0, 0), 1), f)
            main(
                [
                    "--format",
                    "dsfm",
                    "--language",
                    "c",
                    "--input",
                    str(ds),
                    "--pairs",
                    str(dp),
                    "--output",
                    str(dout),
                    "--strategies",
                    "SE2",
                ]
            )
            with (dout / "codes.pkl").open("rb") as f:
                self.assertNotEqual(pickle.load(f), CASES["SE2"])
                self.assertEqual(pickle.load(f), CASES["SE2"])


if __name__ == "__main__":
    unittest.main()
