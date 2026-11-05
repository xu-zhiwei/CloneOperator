"""Release checks for paper numbering, finite composition, and broader C sites."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC))
from sct import compose_all51, create_operator, list_operators

FIXTURES = {
    "fixed_array": "int f(int n){int a[2]={3,4};int x=n;return x+a[0];}",
    "record": "struct S{int value;}; int f(int n){struct S a={2};int x=n;return x+a.value;}",
    "vla": "int f(int n){int a[n];int x=n; a[0]=2;return x+a[0];}",
    "local_with_pointer": "int f(int n){int x=n;int *p=&x;int y=3;return *p+y;}",
}


class ReleaseTests(unittest.TestCase):
    def test_paper_mapping_for_all_51_operators(self):
        rows = list_operators()
        self.assertEqual(len(rows), 51)
        self.assertEqual(len({r["implementation_id"] for r in rows}), 51)
        expected = {"WC4": "WC6", "WC5": "WC4", "WC6": "WC8", "WC7": "WC5",
                    "WC8": "WC7", "SE6": "SE7", "SE7": "SE6", "CC5": "CC6", "CC6": "CC5"}
        self.assertEqual({r["paper_id"]: r["implementation_id"] for r in rows
                          if r["paper_id"] != r["implementation_id"]}, expected)
        for language in ("java", "c"):
            for row in rows:
                self.assertEqual(create_operator(row["paper_id"], language).strategy_id,
                                 row["implementation_id"])
        result = create_operator("WC4", "c").apply("int f(void){return 2+3;}")
        self.assertEqual(result.successful, 1)
        self.assertRegex(result.code, r"return\s+\(?5\)?;")

    def test_entry_insertions_accept_broader_contexts(self):
        sources = list(FIXTURES.values()) + ["int f(int n){end:return n;}"]
        for source in sources:
            for sid in ("SD2", "SS2", "CC2", "CL1"):
                with self.subTest(source=source, sid=sid):
                    result = create_operator(sid, "c").apply(source)
                    self.assertEqual(result.successful, 1)
                    self.assertNotEqual(result.code, source)
                    macro = "#define N 3\n" + source
                    self.assertEqual(create_operator(sid, "c")(macro), macro)

    def test_no_function_wide_array_veto(self):
        result = create_operator("WC3", "c").apply(FIXTURES["local_with_pointer"])
        self.assertGreater(result.successful, 0)
        result = create_operator("WC3", "c").apply("int f(int n){int a[n];return 3;}")
        self.assertGreater(result.successful, 0)

    def test_composition_is_reproducible_and_replayable(self):
        for language, source in [("c", FIXTURES["fixed_array"]),
                                 ("java", "int f(int n){int x=n+2;return x;}")]:
            result = compose_all51(source, language)
            self.assertEqual(result, compose_all51(source, language))
            self.assertEqual(result["attempted_operators"], 51)
            self.assertTrue(result["effectively_changed"])
            current = source.encode("utf-8")
            for stage in result["trace"]:
                for change in stage["changes"]:
                    for edit in sorted(change["edits"], key=lambda e:e["start_byte"], reverse=True):
                        a, b = edit["start_byte"], edit["end_byte"]
                        self.assertEqual(current[a:b].decode("utf-8"), edit["before"])
                        current = current[:a] + edit["after"].encode("utf-8") + current[b:]
                    self.assertEqual(hashlib.sha256(current).hexdigest(), change["after_sha256"])
            self.assertEqual(current.decode("utf-8"), result["code"])

    def test_cli_uses_paper_ids_and_preserves_existing_outputs(self):
        from sct.__main__ import main
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output, log = root / "in.c", root / "out.c", root / "trace.json"
            source.write_text("int f(void){return 2+3;}")
            args = ["--language", "c", "--operator", "WC4", "--input", str(source),
                    "--output", str(output), "--log", str(log)]
            main(args)
            data = json.loads(log.read_text())
            self.assertEqual(data["paper_id"], "WC4")
            self.assertEqual(data["strategy_id"], "WC6")
            before = output.read_bytes()
            with self.assertRaises(SystemExit):
                main(args)
            self.assertEqual(output.read_bytes(), before)

    def test_released_legacy_names_resolve(self):
        from operators import IdentifierRename, ConditionReplace
        from operators.identifier_rename import IdentifierRename as LegacyRename
        self.assertIs(IdentifierRename, LegacyRename)
        source = "int sign(int n){if(n==0)return 0;else return 1;}"
        self.assertNotEqual(ConditionReplace(mode="if_to_switch_nesting")(source), source)

    @unittest.skipUnless(shutil.which("gcc"), "GCC required for C execution validation")
    def test_broader_fixtures_compile_and_execute_with_ubsan(self):
        tail = '\nint main(void){for(int n=1;n<10;n++)printf("%d\\n",f(n));return 0;}\n'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, source in FIXTURES.items():
                result = compose_all51(source, "c", program_id=name)
                self.assertTrue(result["effectively_changed"])
                for opt in ("-O0", "-O2"):
                    outputs = []
                    for kind, text in (("original", source), ("transformed", result["code"])):
                        path = root / f"{name}_{kind}.c"
                        binary = root / f"{name}_{kind}"
                        path.write_text("#include <stdio.h>\n" + text + tail)
                        built = subprocess.run(["gcc", "-std=c11", "-pedantic-errors", opt,
                                                "-fsanitize=undefined", "-fno-sanitize-recover=undefined",
                                                str(path), "-o", str(binary)], capture_output=True, timeout=20)
                        self.assertEqual(built.returncode, 0, built.stderr.decode())
                        run = subprocess.run([str(binary)], capture_output=True, timeout=5)
                        self.assertEqual(run.returncode, 0, run.stderr.decode())
                        self.assertEqual(run.stderr, b"")
                        outputs.append(run.stdout)
                    self.assertEqual(*outputs, msg=(name, opt))


if __name__ == "__main__":
    unittest.main()
