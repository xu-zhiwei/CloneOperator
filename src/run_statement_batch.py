import argparse
import os
import sys

src_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(src_dir)

from operators.statement_reorder import StatementReorder


def collect_java_files(input_dir: str):
    java_files = []
    for root, _, files in os.walk(input_dir):
        for name in files:
            if name.endswith(".java"):
                java_files.append(os.path.join(root, name))
    return java_files


def to_output_path(file_path: str, input_dir: str, output_dir: str) -> str:
    rel_path = os.path.relpath(file_path, input_dir)
    return os.path.join(output_dir, rel_path)


def main():
    parser = argparse.ArgumentParser(description="Batch safe Java statement reorder.")
    parser.add_argument("--input-dir", required=True, help="Input directory containing Java files.")
    parser.add_argument("--output-dir", required=True, help="Output directory for transformed files.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed placeholder for API consistency.")
    parser.add_argument("--max-swaps", type=int, default=20, help="Maximum swaps per file.")
    parser.add_argument(
        "--mode",
        choices=["all", "single"],
        default="all",
        help="Apply one swap or multiple swaps per file.",
    )
    parser.add_argument(
        "--reorder-types",
        default="adjacent_single_decl_init",
        help=(
            "Comma-separated reorder types. "
            "Supported: adjacent_single_decl_init, adjacent_single_decl_optional_init, "
            "adjacent_multi_decl, non_adjacent_decl_run"
        ),
    )
    args = parser.parse_args()

    input_dir = os.path.abspath(args.input_dir)
    output_dir = os.path.abspath(args.output_dir)

    if not os.path.isdir(input_dir):
        print(f"Error: input dir does not exist: {input_dir}")
        return

    java_files = collect_java_files(input_dir)
    if not java_files:
        print(f"No Java files found in: {input_dir}")
        return

    operator = StatementReorder(
        seed=args.seed,
        max_swaps=args.max_swaps,
        mode=args.mode,
        enabled_reorders=args.reorder_types,
    )
    changed = 0

    for src_file in java_files:
        with open(src_file, "r", encoding="utf-8") as f:
            code = f.read()

        new_code = operator(code)
        if new_code != code:
            changed += 1

        dst_file = to_output_path(src_file, input_dir, output_dir)
        os.makedirs(os.path.dirname(dst_file), exist_ok=True)
        with open(dst_file, "w", encoding="utf-8") as f:
            f.write(new_code)

    print(f"Processed files: {len(java_files)}")
    print(f"Changed files: {changed}")
    print(f"Output dir: {output_dir}")


if __name__ == "__main__":
    main()
