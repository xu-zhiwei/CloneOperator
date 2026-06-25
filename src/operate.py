"""Apply one clone operator to a Java source file."""

import argparse
from pathlib import Path

from operators import (
    ConditionReplace,
    ConstantReplace,
    IdentifierRename,
    IdentifierReorder,
    LoopReplace,
    RedundantConstantInsert,
    RedundantStatementInsert,
    StatementReorder,
)


OPERATOR_FACTORIES = {
    "identifier-rename": lambda seed: IdentifierRename(seed=seed),
    "identifier-reorder": lambda seed: IdentifierReorder(seed=seed),
    "constant-replace": lambda seed: ConstantReplace(),
    "redundant-constant-insert": lambda seed: RedundantConstantInsert(seed=seed),
    "loop-replace": lambda seed: LoopReplace(seed=seed),
    "condition-replace": lambda seed: ConditionReplace(seed=seed),
    "statement-reorder": lambda seed: StatementReorder(seed=seed),
    "redundant-statement-insert": lambda seed: RedundantStatementInsert(seed=seed),
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply a semantic-preserving transformation to Java source code."
    )
    parser.add_argument("operator", choices=sorted(OPERATOR_FACTORIES))
    parser.add_argument("input", type=Path, help="Input Java source file")
    parser.add_argument("-o", "--output", type=Path, help="Output file; stdout if omitted")
    parser.add_argument("-k", type=int, default=1, help="Number of applications")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    source = args.input.read_text(encoding="utf-8")
    operator = OPERATOR_FACTORIES[args.operator](args.seed)
    transformed = operator(source, k=args.k)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(transformed, encoding="utf-8")
    else:
        print(transformed)


if __name__ == "__main__":
    main()
