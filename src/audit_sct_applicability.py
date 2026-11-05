"""Bounded method audit: applicability and syntax, without detector execution."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

import pandas as pd
import javalang
from operators.registry import REGISTRY, create_strategy


def java_parseable(code):
    try:
        tokens = javalang.tokenizer.tokenize(code)
        javalang.parser.Parser(tokens).parse_member_declaration()
        return True
    except (
        javalang.parser.JavaSyntaxError,
        javalang.tokenizer.LexerError,
        TypeError,
        IndexError,
    ):
        return False


def audit(source, limit, strategy_ids, seed=42, language="java"):
    table = pd.read_csv(
        source, sep="\t", header=None, nrows=limit, keep_default_na=False
    )
    methods = [
        (str(row[0]), str(row[1])) for row in table.itertuples(index=False, name=None)
    ]
    report = {
        "schema_version": 2,
        "source": str(Path(source).resolve()),
        "sample_rule": "first rows in source order",
        "rows": len(methods),
        "seed": seed,
        "validation": "method syntax only; no compilation context or behavior verification",
        "sample_sha256": hashlib.sha256(
            json.dumps(methods, ensure_ascii=False).encode()
        ).hexdigest(),
        "strategies": {},
    }
    from operators.base.language import make_parser

    syntax_parser = make_parser(language)
    parseable = (
        java_parseable
        if language == "java"
        else lambda code: not syntax_parser.parse(
            code.encode("utf-8")
        ).root_node.has_error
    )
    report["language"] = language
    report["implementation"] = "sct-v3"
    report["standard"] = "C11" if language == "c" else "Java"
    report[
        "validation"
    ] = "syntax only; no compilation context or behavior verification"
    original_parseable = {i: parseable(code) for i, code in methods}
    for sid in strategy_ids:
        operator = create_strategy(sid, seed=seed, language=language)
        start = time.monotonic()
        reasons = Counter()
        changed = 0
        invalid = []
        errors = []
        eligible = 0
        sample_records = []
        for source_id, code in methods:
            try:
                result = operator.apply(code)
                eligible += result.eligible_candidates
                reasons.update(item["reason"] for item in result.rejections)
                if result.successful:
                    changed += 1
                    output_parseable = parseable(result.code)
                    if original_parseable[source_id] and not output_parseable:
                        invalid.append(source_id)
                    sample_records.append(
                        {
                            "id": source_id,
                            "successful": result.successful,
                            "construction": result.changes[0]["construction"],
                            "original_java_parseable": original_parseable[source_id],
                            "transformed_java_parseable": output_parseable,
                        }
                    )
            except Exception as exc:
                errors.append({"id": source_id, "error": repr(exc)})
        if language == "c":
            for record in sample_records:
                record["original_c_parseable"] = record.pop("original_java_parseable")
                record["transformed_c_parseable"] = record.pop(
                    "transformed_java_parseable"
                )
        report["strategies"][sid] = {
            "changed": changed,
            "unchanged": len(methods) - changed - len(errors),
            "eligible_candidates": eligible,
            "rejection_reasons": dict(reasons),
            "new_java_parse_failures": invalid,
            "errors": errors,
            "accepted_methods": sample_records,
            "elapsed_seconds": round(time.monotonic() - start, 4),
        }
        if language == "c":
            result = report["strategies"][sid]
            result["new_c_parse_failures"] = result.pop("new_java_parse_failures")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", choices=("java", "c"), default="java")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=128)
    parser.add_argument("--strategies", default=",".join(REGISTRY))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("limit must be positive")
    if args.output.exists():
        parser.error("output exists")
    ids = [sid.strip().upper() for sid in args.strategies.split(",")]
    if any(sid not in REGISTRY for sid in ids):
        parser.error("unknown strategy")
    try:
        report = audit(args.input, args.limit, ids, args.seed, args.language)
    except (OSError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    for sid, result in report["strategies"].items():
        print(
            f'{sid} changed={result["changed"]}/{report["rows"]} errors={len(result["errors"])} new_parse_failures={len(result["new_" + ("c" if args.language == "c" else "java") + "_parse_failures"])}'
        )


if __name__ == "__main__":
    main()
