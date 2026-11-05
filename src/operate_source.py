"""Transform one Java or C source file with an explicit SCT strategy chain."""
import argparse
import json
from pathlib import Path
from operate_sct import parse_strategies, transform


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--language", choices=("java", "c"), default="java")
    parser.add_argument("--strategies", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--options", type=Path)
    args = parser.parse_args(argv)
    log_path = args.output.with_name(args.output.name + ".applications.jsonl")
    if args.output.exists() or log_path.exists():
        parser.error("output or application log already exists")
    try:
        options = (
            json.loads(args.options.read_text(encoding="utf-8")) if args.options else {}
        )
        if not isinstance(options, dict) or any(
            not isinstance(v, dict) for v in options.values()
        ):
            raise ValueError("options must map strategy IDs to objects")
        from operators.registry import get_registry

        if set(k.upper() for k in options) - get_registry(args.language).keys():
            raise ValueError("options contains unknown strategy IDs")
        options = {key.upper(): value for key, value in options.items()}
        chain = parse_strategies(args.strategies, args.seed, options, args.language)
        suffix = "_".join(f"{op.strategy_id}k{k}" for op, k in chain)
        if args.language == "c" and "c_" + suffix not in args.output.name:
            raise ValueError(f"C output name must contain c_{suffix}")
        code, records = transform(args.input.read_text(encoding="utf-8"), chain)
        configuration = dict(
            language=args.language,
            implementation="sct-v3",
            standard="C11" if args.language == "c" else "Java",
            seed=args.seed,
            strategies=args.strategies,
            options=options,
            input=str(args.input.resolve()),
        )
        # Exclusive creation preserves existing artifacts even if another process races.
        with log_path.open("x", encoding="utf-8") as log:
            with args.output.open("x", encoding="utf-8") as output:
                output.write(code)
            log.write(
                json.dumps(dict(configuration=configuration), ensure_ascii=False) + "\n"
            )
            for record in records:
                log.write(json.dumps(record, ensure_ascii=False) + "\n")
            log.write(json.dumps(dict(completed=True)) + "\n")
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
