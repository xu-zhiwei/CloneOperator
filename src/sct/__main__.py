"""Transform a Java/C file with paper IDs or the ALL51 composition."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from . import PROFILE, compose_all51, create_operator, list_operators


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--list", action="store_true", help="Print the 51 paper operators as JSON")
    choice.add_argument("--operator", help="One paper operator ID, e.g. WC4")
    choice.add_argument("--all51", action="store_true", help="Apply the finite seven-phase composition")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, help="New output file, or stdout when omitted")
    parser.add_argument("--log", type=Path, help="New JSON file containing the edit trace")
    parser.add_argument("--language", choices=("java", "c"), default="java")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--program-id", help="Stable ID used to seed the ALL51 schedule")
    parser.add_argument("-k", type=int, default=1, help="Successful application limit for --operator")
    args = parser.parse_args(argv)
    if args.list:
        print(json.dumps(list_operators(), indent=2))
        return
    if args.input is None:
        parser.error("--input is required for transformation")
    if args.k < 0 or (args.all51 and args.k != 1):
        parser.error("-k must be nonnegative and applies only to --operator")
    paths = [p.resolve() for p in (args.output, args.log) if p is not None]
    if len(set(paths)) != len(paths):
        parser.error("--output and --log must name different files")
    for path in paths:
        if path.exists():
            parser.error(f"refusing to overwrite {path}")
    try:
        source = args.input.read_text(encoding="utf-8")
        if args.all51:
            result = compose_all51(source, args.language, args.seed, args.program_id)
        else:
            result = asdict(create_operator(args.operator, args.language, args.seed).apply(source, args.k))
            result.update(paper_id=args.operator.upper(), seed=args.seed,
                          operator_profile=PROFILE if args.language == "c" else "SCT51_JAVA")
        code = result.pop("code")
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(code)
        else:
            sys.stdout.write(code)
        if args.log:
            with args.log.open("x", encoding="utf-8") as stream:
                json.dump(result, stream, indent=2)
                stream.write("\n")
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
