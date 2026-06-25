import argparse
import json
import pickle
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pycparser
from pycparser import c_ast, c_generator
from tree_sitter import Language, Parser
import tree_sitter_java as tsjava


NO_INIT = "<NO_INIT>"

# Fallback regex for parse failures.
JAVA_DECL_RE = re.compile(
    r"(?P<type>[A-Za-z_][\w<>\[\],\s?&.]*)\s+"
    r"(?P<name>[A-Za-z_]\w*)\s*(=\s*(?P<init>[^;]+))?;"
)
C_DECL_RE = re.compile(
    r"(?P<type>(?:unsigned|signed|long|short|const|volatile|static|register|"
    r"extern|struct\s+\w+|enum\s+\w+|union\s+\w+|[A-Za-z_]\w+)"
    r"(?:[\s\*]+[A-Za-z_]\w+|[\s\*])*)\s+"
    r"(?P<name>[A-Za-z_]\w*)\s*(=\s*(?P<init>[^;]+))?;"
)


def iter_pickle_stream(path: Path) -> Iterable[str]:
    with path.open("rb") as f:
        while True:
            try:
                yield pickle.load(f)
            except EOFError:
                break


def clean_text(value: str | None, default: str = NO_INIT) -> str:
    if value is None:
        return default
    value = re.sub(r"\s+", " ", str(value)).strip()
    return value if value else default


def c_type_to_str(type_node: c_ast.Node) -> str:
    if isinstance(type_node, c_ast.TypeDecl):
        return c_type_to_str(type_node.type)
    if isinstance(type_node, c_ast.IdentifierType):
        return " ".join(type_node.names)
    if isinstance(type_node, c_ast.PtrDecl):
        return f"{c_type_to_str(type_node.type)} *"
    if isinstance(type_node, c_ast.ArrayDecl):
        return f"{c_type_to_str(type_node.type)} []"
    if isinstance(type_node, c_ast.Struct):
        return f"struct {type_node.name or '<anonymous>'}"
    if isinstance(type_node, c_ast.Union):
        return f"union {type_node.name or '<anonymous>'}"
    if isinstance(type_node, c_ast.Enum):
        return f"enum {type_node.name or '<anonymous>'}"
    if isinstance(type_node, c_ast.FuncDecl):
        return "function"
    return type(type_node).__name__


class CVariableVisitor(c_ast.NodeVisitor):
    def __init__(self) -> None:
        self.generator = c_generator.CGenerator()
        self.variables: list[tuple[str, str, str]] = []

    def visit_Decl(self, node: c_ast.Decl) -> None:
        # Skip function declarations/definitions.
        if isinstance(node.type, c_ast.FuncDecl):
            return
        if node.name:
            var_type = clean_text(c_type_to_str(node.type), default="<UNKNOWN_TYPE>")
            var_name = clean_text(node.name, default="<UNKNOWN_NAME>")
            init_value = (
                clean_text(self.generator.visit(node.init)) if node.init is not None else NO_INIT
            )
            self.variables.append((var_type, var_name, init_value))
        self.generic_visit(node)


def extract_c_variables(code: str, parser: pycparser.CParser) -> tuple[list[tuple[str, str, str]], str]:
    attempts = [code, f"void __cursor_wrapper__() {{\n{code}\n}}"]
    for source in attempts:
        try:
            ast = parser.parse(source)
            visitor = CVariableVisitor()
            visitor.visit(ast)
            return visitor.variables, "parser"
        except Exception:
            continue

    variables: list[tuple[str, str, str]] = []
    for match in C_DECL_RE.finditer(code):
        var_type = clean_text(match.group("type"), default="<UNKNOWN_TYPE>")
        var_name = clean_text(match.group("name"), default="<UNKNOWN_NAME>")
        init_value = clean_text(match.group("init"))
        variables.append((var_type, var_name, init_value))
    return variables, "regex"


def extract_java_variables(code: str, parser: Parser) -> tuple[list[tuple[str, str, str]], str]:
    code_bytes = code.encode("utf-8", errors="ignore")
    try:
        tree = parser.parse(code_bytes)
        variables: list[tuple[str, str, str]] = []
        stack = [tree.root_node]
        while stack:
            node = stack.pop()
            if node.type in ("local_variable_declaration", "field_declaration"):
                type_node = node.child_by_field_name("type")
                var_type = (
                    clean_text(code_bytes[type_node.start_byte : type_node.end_byte].decode("utf-8"))
                    if type_node
                    else "<UNKNOWN_TYPE>"
                )
                for child in node.children:
                    if child.type != "variable_declarator":
                        continue
                    name_node = child.child_by_field_name("name")
                    value_node = child.child_by_field_name("value")
                    var_name = (
                        clean_text(code_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8"))
                        if name_node
                        else "<UNKNOWN_NAME>"
                    )
                    init_value = (
                        clean_text(code_bytes[value_node.start_byte : value_node.end_byte].decode("utf-8"))
                        if value_node
                        else NO_INIT
                    )
                    variables.append((var_type, var_name, init_value))
            stack.extend(node.children)
        return variables, "parser"
    except Exception:
        variables = []
        for match in JAVA_DECL_RE.finditer(code):
            var_type = clean_text(match.group("type"), default="<UNKNOWN_TYPE>")
            var_name = clean_text(match.group("name"), default="<UNKNOWN_NAME>")
            init_value = clean_text(match.group("init"))
            variables.append((var_type, var_name, init_value))
        return variables, "regex"


def sorted_counter_dict(counter: Counter) -> dict[str, int]:
    return {k: v for k, v in sorted(counter.items(), key=lambda x: (-x[1], x[0]))}


def sorted_nested_counter_dict(counters: dict[str, Counter]) -> dict[str, dict[str, int]]:
    return {
        outer_key: sorted_counter_dict(inner_counter)
        for outer_key, inner_counter in sorted(counters.items(), key=lambda x: x[0])
    }


def analyze_dataset(dataset_name: str, dataset_dir: Path) -> dict:
    code_path = dataset_dir / "codes.pkl"
    if not code_path.exists():
        raise FileNotFoundError(f"Missing file: {code_path}")

    type_counter: Counter = Counter()
    name_counter: Counter = Counter()
    init_counter: Counter = Counter()
    type_name_counter: dict[str, Counter] = defaultdict(Counter)
    type_init_counter: dict[str, Counter] = defaultdict(Counter)

    parser_stats = {"parser": 0, "regex": 0}
    sample_count = 0
    variable_count = 0

    c_parser = pycparser.CParser()
    java_parser = Parser(Language(tsjava.language()))

    for code in iter_pickle_stream(code_path):
        sample_count += 1
        if not isinstance(code, str):
            continue

        if dataset_name == "OJClone":
            variables, method = extract_c_variables(code, c_parser)
        else:
            variables, method = extract_java_variables(code, java_parser)
        parser_stats[method] += 1

        for var_type, var_name, init_value in variables:
            type_counter[var_type] += 1
            name_counter[var_name] += 1
            init_counter[init_value] += 1
            type_name_counter[var_type][var_name] += 1
            type_init_counter[var_type][init_value] += 1
            variable_count += 1

    return {
        "dataset": dataset_name,
        "samples": sample_count,
        "variables": variable_count,
        "parse_method_usage": parser_stats,
        "variable_type_frequency": sorted_counter_dict(type_counter),
        "variable_name_frequency": sorted_counter_dict(name_counter),
        "variable_init_value_frequency": sorted_counter_dict(init_counter),
        "variable_name_frequency_by_type": sorted_nested_counter_dict(type_name_counter),
        "variable_init_value_frequency_by_type": sorted_nested_counter_dict(type_init_counter),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Variable frequency statistics for clone datasets.")
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data",
        help="Data root containing BigCloneBench/GCJ/OJClone subfolders.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "variable_frequency_stats.json",
        help="Output json file path.",
    )
    args = parser.parse_args()

    datasets = ["BigCloneBench", "GCJ", "OJClone"]
    results: dict[str, dict] = {}

    overall_type: Counter = Counter()
    overall_name: Counter = Counter()
    overall_init: Counter = Counter()
    overall_samples = 0
    overall_variables = 0
    overall_parse = Counter()
    overall_type_name: dict[str, Counter] = defaultdict(Counter)
    overall_type_init: dict[str, Counter] = defaultdict(Counter)

    for ds in datasets:
        ds_dir = args.data_root / ds
        ds_result = analyze_dataset(ds, ds_dir)
        results[ds] = ds_result

        overall_samples += ds_result["samples"]
        overall_variables += ds_result["variables"]
        overall_parse.update(ds_result["parse_method_usage"])
        overall_type.update(ds_result["variable_type_frequency"])
        overall_name.update(ds_result["variable_name_frequency"])
        overall_init.update(ds_result["variable_init_value_frequency"])
        for var_type, per_type_name_freq in ds_result["variable_name_frequency_by_type"].items():
            overall_type_name[var_type].update(per_type_name_freq)
        for var_type, per_type_init_freq in ds_result["variable_init_value_frequency_by_type"].items():
            overall_type_init[var_type].update(per_type_init_freq)

    output = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_root": str(args.data_root),
        "datasets": results,
        "overall": {
            "samples": overall_samples,
            "variables": overall_variables,
            "parse_method_usage": dict(overall_parse),
            "variable_type_frequency": sorted_counter_dict(overall_type),
            "variable_name_frequency": sorted_counter_dict(overall_name),
            "variable_init_value_frequency": sorted_counter_dict(overall_init),
            "variable_name_frequency_by_type": sorted_nested_counter_dict(overall_type_name),
            "variable_init_value_frequency_by_type": sorted_nested_counter_dict(overall_type_init),
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Saved variable statistics to: {args.output}")


if __name__ == "__main__":
    main()
