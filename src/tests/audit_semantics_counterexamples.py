"""Reproduce semantic audit findings without changing operator implementations.

By default, exit zero means the four historical counterexamples are repaired
in these tested inputs. --expect-unsafe reproduces the historical audit criteria. Requires the existing Java compiler module and GCC.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from operators import create_strategy

CASES = [
    dict(name="java_constructor_parameter_string_field", language="java", strategy="SE1", seed=42,
         code='public class T { String x="v"; String m(){class L {L(int x){}} return x+1;} public static void main(String[] a){System.out.print(new T().m());}}',
         expected="output_changed"),
    dict(name="java_constructor_parameter_byte_field", language="java", strategy="SE6", seed=42,
         code='public class T { byte x=1; int m(){class L {L(int x){}} x+=1; return x;} public static void main(String[] a){System.out.print(new T().m());}}',
         expected="compilation_rejected"),
    dict(name="c_equality_expression_tree", language="c", strategy="SE1", seed=0,
         code='int f(void){int a=2;int b=2;int c=0;return a==b!=c;} int main(void){return f();}',
         expected="exit_status_changed"),
    dict(name="c_signed_overflow_int32", language="c", strategy="SE1", seed=42,
         code='int f(void){int a=2147483647;int b=2147483647;int c=1;return a-b+c;} int main(void){return f();}',
         expected="undefined_behavior_introduced"),
]


def execute(command, cwd):
    p = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=30)
    # Temporary directory paths are irrelevant to the finding.
    return dict(command=command, returncode=p.returncode,
                stdout=p.stdout, stderr=p.stderr.replace(str(cwd), "<workdir>"))


def compile_run(code, language, workdir):
    workdir.mkdir()
    source = "T.java" if language == "java" else "t.c"
    (workdir / source).write_text(code, encoding="utf-8")
    compiler = (["java", "-m", "jdk.compiler/com.sun.tools.javac.Main", source]
                if language == "java" else
                ["gcc", "-std=c11", "-pedantic-errors", "-O0", "-fsanitize=undefined",
                 "-fno-sanitize-recover=all", source, "-o", "program"])
    compiled = execute(compiler, workdir)
    run = None
    if compiled["returncode"] == 0:
        run = execute(["java", "-cp", ".", "T"] if language == "java" else ["./program"], workdir)
    return dict(compile=compiled, run=run)


def audit(expect_unsafe=False):
    records = []
    with tempfile.TemporaryDirectory(prefix="sct-semantics-audit-") as directory:
        root = Path(directory)
        for i, case in enumerate(CASES):
            result = create_strategy(case["strategy"], language=case["language"], seed=case["seed"]).apply(case["code"])
            before = compile_run(case["code"], case["language"], root / f"{i}-before")
            after = compile_run(result.code, case["language"], root / f"{i}-after")
            if expect_unsafe:
                assert result.successful == 1, result
            assert before["compile"]["returncode"] == 0 and before["run"] is not None, before
            assert not before["run"]["stderr"], before
            kind = case["expected"]
            if kind == "compilation_rejected":
                confirmed = after["compile"]["returncode"] != 0
            else:
                assert after["compile"]["returncode"] == 0, after
                if kind == "output_changed":
                    confirmed = before["run"]["stdout"] != after["run"]["stdout"]
                elif kind == "exit_status_changed":
                    confirmed = before["run"]["returncode"] != after["run"]["returncode"]
                else:
                    confirmed = "runtime error: signed integer overflow" in after["run"]["stderr"]
            if expect_unsafe:
                assert confirmed, (case, before, after)
            else:
                assert after["compile"]["returncode"] == 0 and after["run"] is not None, after
                assert all(before["run"][key] == after["run"][key] for key in ("returncode", "stdout", "stderr")), (case, before, after)
            records.append(dict(**case, application=asdict(result), before=before, after=after, historical_failure_reproduced=confirmed, repaired=not confirmed))
    return dict(conclusion="Historical unsafe criteria reproduced" if expect_unsafe else "Four historical counterexamples repaired in the tested inputs",
                scope="Four counterexamples, two root causes. Not an exhaustive audit of eighty implementations.",
                c_overflow_platform="The fourth case uses the tested GCC host's 32 bit int.", cases=records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expect-unsafe", action="store_true", help="Use the historical pre-repair failure criteria")
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        parser.error("Refusing to overwrite an existing audit record")
    report = audit(expect_unsafe=args.expect_unsafe)
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    print(report["conclusion"] + ". This is bounded regression evidence, not a general semantic guarantee.")
