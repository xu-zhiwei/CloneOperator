"""Explicit, non-overwriting ASTNN/DSFM generation with SCT strategy records."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import pickle
import shutil

from operators.registry import create_strategy


def parse_strategies(spec, seed, options=None, language="java"):
    options = options or {}
    chain = []
    for item in spec.split(","):
        strategy_id, separator, intensity = item.strip().partition(":")
        if not strategy_id:
            raise ValueError("strategy chain must contain nonempty IDs")
        k = int(intensity) if separator else 1
        if k < 0:
            raise ValueError("intensity must be nonnegative")
        settings = dict(options.get(strategy_id.upper(), {}))
        if "language" in settings:
            raise ValueError("language is a chain-level setting")
        settings["seed"] = seed
        chain.append((create_strategy(strategy_id, language=language, **settings), k))
    return chain


def transform(code, chain):
    records = []
    for operator, k in chain:
        result = operator.apply(code, k)
        code = result.code
        record = asdict(result)
        record.pop("code")
        records.append(record)
    return code, records


def pickle_stream(path):
    with path.open("rb") as stream:
        while True:
            try:
                yield pickle.load(stream)
            except EOFError:
                return


def generate_astnn(source, output, pairs, chain, log):
    import pandas as pd

    pair_table = pd.read_pickle(pairs)
    ids = set(pair_table["id1"].astype(int)) | set(pair_table["id2"].astype(int))
    table = pd.read_csv(
        source, sep="\t", header=None, names=["id", "code"], keep_default_na=False
    )
    for index, row in table.iterrows():
        if int(row["id"]) in ids:
            code, records = transform(row["code"], chain)
            table.at[index, "code"] = code
            log.write(
                json.dumps(
                    {"id": int(row["id"]), "strategies": records}, ensure_ascii=False
                )
                + "\n"
            )
    with output.open("x", encoding="utf-8", newline="") as stream:
        table.to_csv(stream, sep="\t", header=False, index=False)


def generate_dsfm(source, output, pairs, chain, log):
    ids = set()
    for (first, second), _label in pickle_stream(pairs):
        ids.update((first, second))
    shutil.copytree(source, output)
    for filename in ("subtrees.pkl", "codes.pkl"):
        (output / filename).unlink(missing_ok=True)
    with (output / "codes.pkl").open("xb") as stream:
        for index, code in enumerate(pickle_stream(source / "codes.pkl")):
            if index in ids:
                code, records = transform(code, chain)
                log.write(
                    json.dumps({"id": index, "strategies": records}, ensure_ascii=False)
                    + "\n"
                )
            pickle.dump(code, stream)


def main(argv=None, default_format=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--format",
        choices=("astnn", "dsfm"),
        required=default_format is None,
        default=default_format,
    )
    parser.add_argument("--language", choices=("java", "c"), default="java")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pairs", required=True, type=Path)
    parser.add_argument("--strategies", required=True, help="For example SE2:1,SD4:2")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--options", type=Path, help="JSON mapping strategy IDs to constructor settings"
    )
    args = parser.parse_args(argv)
    options = {}
    try:
        if args.options:
            with args.options.open(encoding="utf-8") as stream:
                payload = json.load(stream)
            if not isinstance(payload, dict) or any(
                not isinstance(v, dict) for v in payload.values()
            ):
                parser.error("options must map strategy IDs to JSON objects")
            from operators.registry import REGISTRY

            options = {key.upper(): value for key, value in payload.items()}
            if set(options) - REGISTRY.keys():
                parser.error("options contains unknown strategy IDs")
        chain = parse_strategies(args.strategies, args.seed, options, args.language)
    except (ValueError, TypeError, OSError, RuntimeError) as exc:
        parser.error(str(exc))
    suffix = "_".join(f"{operator.strategy_id}k{k}" for operator, k in chain)
    if args.language == "c":
        suffix = "c_" + suffix
    if suffix not in args.output.name:
        parser.error(
            f"output name must contain {suffix!r} to identify the strategy settings"
        )
    log_path = args.output.with_name(args.output.name + ".applications.jsonl")
    if args.output.exists() or log_path.exists():
        parser.error(
            "output or application log already exists; choose a new destination"
        )
    if not args.input.exists() or not args.pairs.is_file():
        parser.error("input and pairs must exist")
    if args.format == "dsfm" and not (args.input / "codes.pkl").is_file():
        parser.error("DSFM input must contain codes.pkl")
    if args.format == "dsfm" and args.input.resolve() in args.output.resolve().parents:
        parser.error("DSFM output must be outside the input directory")
    with log_path.open("x", encoding="utf-8") as log:
        log.write(
            json.dumps(
                {
                    "configuration": {
                        "format": args.format,
                        "language": args.language,
                        "standard": "C11" if args.language == "c" else "Java",
                        "input": str(args.input.resolve()),
                        "pairs": str(args.pairs.resolve()),
                        "strategies": args.strategies,
                        "seed": args.seed,
                        "options": options,
                        "implementation": "sct-v3",
                    }
                }
            )
            + "\n"
        )
        if args.format == "astnn":
            generate_astnn(args.input, args.output, args.pairs, chain, log)
        else:
            generate_dsfm(args.input, args.output, args.pairs, chain, log)
        log.write(json.dumps({"completed": True}) + "\n")


if __name__ == "__main__":
    main()
