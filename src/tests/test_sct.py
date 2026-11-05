import importlib
import contextlib
import io
import json
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
from operators.sct_strategies import REGISTRY, create_strategy
from operators.sct_core import Context
from sct_cases import CASES, REJECTIONS

JAVA_COMPILER = [shutil.which("javac")] if shutil.which("javac") else None
if JAVA_COMPILER is None and shutil.which("java"):
    probe = subprocess.run(
        ["java", "-m", "jdk.compiler/com.sun.tools.javac.Main", "-version"],
        capture_output=True,
    )
    if probe.returncode == 0:
        JAVA_COMPILER = ["java", "-m", "jdk.compiler/com.sun.tools.javac.Main"]


class StrategyTests(unittest.TestCase):
    def test_all_forty_have_independent_changed_examples(self):
        self.assertEqual(set(REGISTRY), set(CASES))
        self.assertEqual(len(REGISTRY), 51)
        for sid, source in CASES.items():
            with self.subTest(sid=sid):
                op = create_strategy(sid)
                result = op.apply(source)
                self.assertEqual(result.successful, 1, result)
                self.assertNotEqual(result.code, source)
                self.assertFalse(
                    Context(result.code, op.parser).tree.root_node.has_error
                )
                import javalang

                javalang.parse.parse("class T { " + result.code + " }")
                self.assertEqual(result.strategy_id, sid)
                self.assertEqual(len(result.changes), 1)
                self.assertEqual(op(source), result.code)

    def test_all_pending_reject_unsafe_or_inapplicable_examples(self):
        self.assertEqual(len(REJECTIONS), 35)
        for sid, source in REJECTIONS.items():
            with self.subTest(sid=sid):
                result = create_strategy(sid).apply(source)
                self.assertEqual(result.code, source)
                self.assertEqual(result.successful, 0)
                self.assertTrue(result.rejections)

    def test_repeat_seed_unicode_and_global_random(self):
        state = random.getstate()
        for sid, source in CASES.items():
            with self.subTest(sid=sid):
                source = "/* 中文 */ " + source
                a = create_strategy(sid, seed=9).apply(source, 3)
                b = create_strategy(sid, seed=9).apply(source, 3)
                self.assertEqual(a, b)
                self.assertLessEqual(a.successful, 3)
                self.assertTrue(a.code.startswith("/* 中文 */"))
        self.assertEqual(state, random.getstate())

    def test_invalid_input_and_intensity(self):
        for sid in REGISTRY:
            op = create_strategy(sid)
            self.assertEqual(op("int m( {", 2), "int m( {")
            self.assertEqual(op(CASES[sid], 0), CASES[sid])
            for k in (-1, 1.5, True):
                with self.assertRaises(ValueError):
                    op(CASES[sid], k)
        with self.assertRaises(ValueError):
            create_strategy("missing")

    def test_binding_rejects_shadowing_and_arrays(self):
        cases = [
            "int m(int a){ {int a=1; a++;} return a;}",
            "int m(int a[]){a++;return 0;}",
            "int m(){int a[]=null;a++;return 0;}",
        ]
        for source in cases:
            self.assertEqual(create_strategy("SE5")(source), source)

    def test_expression_wrapping_preserves_assignable_positions(self):
        source = "int m(int a){ (a)++; return 1; }"
        self.assertEqual(create_strategy("SE2")(source), source)

    def test_first_flag_mode_keeps_its_definite_assignment_restrictions(self):
        for source in [
            "int m(){int x; do{x=1;}while(x<0);return x;}",
            "int m(){do{return 1;}while(false);}",
            "int m(){int x=0;do{x++;}while(true);}",
        ]:
            self.assertEqual(create_strategy("CL7", mode="first_flag")(source), source)
        source = "int m(){int x=0;while(true){return x;}}"
        self.assertNotEqual(create_strategy("CL8")(source), source)
        source = "int m(){while(1<2){return 1;}}"
        self.assertNotEqual(create_strategy("CL8")(source), source)
        source = "int m(int a){if(a>0){do{return 1;}while(a>1);}else{return 2;}}"
        self.assertEqual(create_strategy("CL7", mode="first_flag")(source), source)

    def test_removal_preserves_checked_exception_context(self):
        cases = [
            (
                "CC3",
                "int m(){try{if(false){throw new java.io.IOException();}}catch(java.io.IOException e){return 2;}return 1;}",
            ),
            (
                "CL2",
                "int m(){try{{boolean f=false;while(f){throw new java.io.IOException();}}}catch(java.io.IOException e){return 2;}return 1;}",
            ),
        ]
        for sid, source in cases:
            self.assertEqual(create_strategy(sid)(source), source)

    def test_single_application_does_not_convert_nested_loops(self):
        source = "int m(){int x=0;while(x<2){while(x<1){x++;}x++;}return x;}"
        result = create_strategy("CL4").apply(source)
        self.assertEqual(result.successful, 1)
        self.assertEqual(result.code.count("while"), 1)

    def test_round_trip_redundancy(self):
        source = "int m(int a){ return a; }"
        for insert, remove in [
            ("CL1", "CL2"),
            ("CC2", "CC3"),
            ("SS2", "SS3"),
            ("SD2", "SD3"),
        ]:
            modified = create_strategy(insert)(source)
            result = create_strategy(remove).apply(modified)
            self.assertEqual(result.successful, 1, (insert, remove, result))

    def test_legacy_imports_and_lightweight_imports(self):
        import operators

        for name, module in operators._legacy.items():
            self.assertIs(
                getattr(operators, name),
                getattr(importlib.import_module("operators." + module), name),
            )
        self.assertIsInstance(operators.IdentifierReorder()("int m(){return 1;}"), str)
        self.assertIsInstance(
            operators.LoopReplace(mode="while_to_for")("int m(){return 1;}"), str
        )
        self.assertIsInstance(
            operators.ConditionReplace(mode="if_to_switch_nesting")(
                "int m(){return 1;}"
            ),
            str,
        )
        for name in (
            "operate_astnn_custom",
            "operate_astnn_combination",
            "operate_dsfm_custom",
            "operate_dsfm_combination",
        ):
            self.assertTrue(callable(importlib.import_module(name).main))

    @unittest.skipUnless(
        JAVA_COMPILER,
        "Java compiler unavailable: compilation and behavior not verified",
    )
    def test_java_equivalence(self):
        extra = [
            (
                "CL7",
                "int m(){int x=0;int c=0;do{x++;if(x<3)continue;if(x>4)break;}while(++c<5);return x*10+c;}",
            ),
            (
                "CL7",
                "int m(){int x=0;int c=0;do{try{x++;continue;}finally{c++;}}while(x<3);return x*10+c;}",
            ),
            ("CL8", "int m(){int x=0;while(x<0){x++;}return x;}"),
            (
                "CL8",
                "int m(){int x=0;int c=0;while(++c<5){x++;if(x<3)continue;break;}return x*10+c;}",
            ),
            (
                "CL8",
                "int m(int a){int x=0;while(10/(a-x)>0){x++;if(x>3)break;}return x;}",
            ),
            (
                "CL7",
                "int m(int a){int x=0;do{x++;if(x>3)break;}while(10/(a-x)>0);return x;}",
            ),
            ("CC8", "int m(int a){int b=0;if(a>0 && ++b>0){b+=2;}return b;}"),
            ("CC9", "int m(int a){int b=0;if(a>0){if(++b>0){b+=2;}}return b;}"),
            ("CC10", "int m(int a){int x;if(++a>0){x=1;}else{x=2;}return x;}"),
            ("WC5", "long m(){return 9223372036854775806L;}"),
            ("SS4", "int m(int a,int b){int sctTemp0=1;a=(a+1)*b;return a+sctTemp0;}"),
            (
                "CC3",
                "int m(){try{if(false){throw new java.io.IOException();}}catch(java.io.IOException e){return 2;}return 1;}",
            ),
            (
                "CL2",
                "int m(){try{{boolean f=false;while(f){throw new java.io.IOException();}}}catch(java.io.IOException e){return 2;}return 1;}",
            ),
        ]
        from sct_extended_cases import EXTENDED_CASES

        scenarios = [
            (sid, {}, source) for sid, source in list(CASES.items()) + extra
        ] + EXTENDED_CASES
        for sid, options, source in scenarios:
            with self.subTest(sid=sid), tempfile.TemporaryDirectory() as directory:
                transformed = create_strategy(sid, **options)(source)
                outputs = []
                for method in (source, transformed):
                    # All example arguments are int; exercise zero, signs and integer boundaries.
                    parameter_count = (
                        source.split("(", 1)[1].split(")", 1)[0].count("int ")
                    )
                    invocations = []
                    for value in ("0", "1", "-1", "2", "2147483647", "-2147483648"):
                        args = ",".join([value] * parameter_count)
                        invocations.append(
                            f"try {{ System.out.println(new T().m({args})); }} catch (Throwable e) {{ System.out.println(e.getClass().getName()); }}"
                        )
                    path = Path(directory) / "T.java"
                    path.write_text(
                        "public class T { "
                        + method
                        + " public static void main(String[] args){"
                        + "".join(invocations)
                        + "}}"
                    )
                    compile_result = subprocess.run(
                        JAVA_COMPILER + [str(path)], capture_output=True, timeout=15
                    )
                    self.assertEqual(
                        compile_result.returncode, 0, compile_result.stderr.decode()
                    )
                    run = subprocess.run(
                        ["java", "-cp", directory, "T"],
                        check=True,
                        capture_output=True,
                        timeout=5,
                    )
                    outputs.append(run.stdout)
                self.assertEqual(*outputs)


class LoopCompilationTests(unittest.TestCase):
    @unittest.skipUnless(JAVA_COMPILER, "Java compiler unavailable")
    def test_infinite_and_constant_loops_preserve_compiler_reachability(self):
        examples = [
            ("CL7", "int m(){do{while(true){}}while(false);}"),
            ("CL7", "int m(){do{if(true)return 1;}while(true);}"),
            ("CL8", "int m(){while(true){}}"),
        ]
        for sid, source in examples:
            with self.subTest(
                sid=sid, source=source
            ), tempfile.TemporaryDirectory() as directory:
                transformed = create_strategy(sid)(source)
                self.assertNotEqual(source, transformed)
                for method in (source, transformed):
                    path = Path(directory) / "T.java"
                    path.write_text("class T{" + method + "}")
                    result = subprocess.run(
                        JAVA_COMPILER + [str(path)], capture_output=True, timeout=15
                    )
                    self.assertEqual(result.returncode, 0, result.stderr.decode())


class GeneratorTests(unittest.TestCase):
    def test_astnn_and_existing_output_protection(self):
        import pandas as pd
        from operate_sct import main

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, pairs, output = (
                root / "source.tsv",
                root / "pairs.pkl",
                root / "out_SE5k1.tsv",
            )
            pd.DataFrame(
                [[1, CASES["SE5"]], [2, CASES["SE5"]], [3, CASES["SE5"]]]
            ).to_csv(source, sep="\t", header=False, index=False)
            pd.DataFrame({"id1": [1], "id2": [2]}).to_pickle(pairs)
            argv = [
                "--format",
                "astnn",
                "--input",
                str(source),
                "--pairs",
                str(pairs),
                "--output",
                str(output),
                "--strategies",
                "SE5:1",
            ]
            options_path = root / "options.json"
            options_path.write_text(json.dumps({"SE5": {"mode": "compound"}}))
            argv += ["--options", str(options_path)]
            main(argv)
            result = pd.read_csv(output, sep="\t", header=None)
            self.assertNotEqual(result.iloc[0, 1], CASES["SE5"])
            self.assertEqual(result.iloc[2, 1], CASES["SE5"])
            before = output.read_bytes()
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(
                io.StringIO()
            ):
                main(argv)
            self.assertEqual(output.read_bytes(), before)
            records = [
                json.loads(line)
                for line in output.with_name(output.name + ".applications.jsonl")
                .read_text()
                .splitlines()
            ]
            self.assertEqual(records[0]["configuration"]["implementation"], "sct-v3")
            self.assertEqual(
                records[0]["configuration"]["options"]["SE5"]["mode"], "compound"
            )
            self.assertIn("a += 1", result.iloc[0, 1])
            self.assertEqual(records[1]["strategies"][0]["successful"], 1)

    def test_dsfm_selection_and_cache(self):
        from operate_sct import main, pickle_stream

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "source", root / "out_SE5k1"
            source.mkdir()
            with (source / "codes.pkl").open("wb") as f:
                for _ in range(3):
                    pickle.dump(CASES["SE5"], f)
            with (source / "test.pkl").open("wb") as f:
                pickle.dump(((0, 1), 1), f)
            (source / "subtrees.pkl").write_bytes(b"old cache")
            main(
                [
                    "--format",
                    "dsfm",
                    "--input",
                    str(source),
                    "--pairs",
                    str(source / "test.pkl"),
                    "--output",
                    str(output),
                    "--strategies",
                    "SE5:1",
                ]
            )
            codes = list(pickle_stream(output / "codes.pkl"))
            self.assertNotEqual(codes[0], CASES["SE5"])
            self.assertEqual(codes[2], CASES["SE5"])
            self.assertFalse((output / "subtrees.pkl").exists())
            self.assertTrue((source / "subtrees.pkl").exists())
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(
                io.StringIO()
            ):
                main(
                    [
                        "--format",
                        "dsfm",
                        "--input",
                        str(source),
                        "--pairs",
                        str(source / "test.pkl"),
                        "--output",
                        str(source / "nested_SE5k1"),
                        "--strategies",
                        "SE5:1",
                    ]
                )


if __name__ == "__main__":
    unittest.main()
