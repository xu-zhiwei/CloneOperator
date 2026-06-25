"""O7 - Redundant Statement Insertion.

Call ``RedundantStatementInsert(...)(code, k=n)`` to insert unused local
statements. ``analyzer_mode`` selects ``def_only``, ``def_use``, ``inc_dec``,
``dec_inc``, or ``random``; sampling options control types, names, and
initializers.
"""

import json
import os
import random
import re
from pathlib import Path

import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from .base_operator import BaseOperator


SUPPORTED_ANALYZER_MODES = {
    "def_only",  # int x = 0;
    "def_use",  # int x = 0; x = 0;
    "inc_dec",  # int x = 0; x++; x--;
    "dec_inc",  # int x = 0; x--; x++;
    "random",  # randomly picks one of the above
}
SUPPORTED_SAMPLING_MODES = {"frequency", "inverse_frequency", "random"}

JAVA_KEYWORDS = {
    "abstract",
    "assert",
    "boolean",
    "break",
    "byte",
    "case",
    "catch",
    "char",
    "class",
    "const",
    "continue",
    "default",
    "do",
    "double",
    "else",
    "enum",
    "extends",
    "final",
    "finally",
    "float",
    "for",
    "goto",
    "if",
    "implements",
    "import",
    "instanceof",
    "int",
    "interface",
    "long",
    "native",
    "new",
    "package",
    "private",
    "protected",
    "public",
    "return",
    "short",
    "static",
    "strictfp",
    "super",
    "switch",
    "synchronized",
    "this",
    "throw",
    "throws",
    "transient",
    "try",
    "void",
    "volatile",
    "while",
    "true",
    "false",
    "null",
}

SAFE_TYPES = {
    "int",
    "long",
    "double",
    "float",
    "boolean",
    "byte",
    "short",
    "char",
    "String",
    "Object",
}
NUMERIC_TYPES = {"int", "long", "double", "float", "byte", "short", "char"}
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_NUMERIC_LITERAL_RE = re.compile(r"^[+-]?\d+([lL]|(\.\d+([eE][+-]?\d+)?)|([fFdD]))?$")

_UNSAFE_AFTER = frozenset(
    {
        "return_statement",
        "throw_statement",
        "break_statement",
        "continue_statement",
    }
)


class Sampler:
    _shared_seed = 42

    @classmethod
    def reset_shared_seed(cls, seed: int):
        Sampler._shared_seed = seed

    def __init__(self):
        self.seed = Sampler._shared_seed
        self.rng = random.Random(self.seed)

    def renew_rng(self):
        Sampler._shared_seed += 1
        self.seed = Sampler._shared_seed
        self.rng = random.Random(self.seed)


class RandomSampler(Sampler):
    def choice(self, values):
        if not values:
            raise ValueError("Cannot choose from an empty sequence")
        self.renew_rng()
        return self.rng.choice(values)

    def sample(self, population, k: int):
        self.renew_rng()
        return self.rng.sample(population, k)


class WeightedSampler(Sampler):
    def __init__(self, strategy: str, freq_map: dict[str, int]):
        super().__init__()
        self.strategy = strategy
        self.freq_map = freq_map

    def pick(self, avoid_exist_if_possible: set[str] | None = None) -> str:
        items = list(self.freq_map.items())
        values = [k for k, _ in items]
        freqs = [max(1, int(v)) for _, v in items]

        if not values:
            raise ValueError("Cannot sample from empty frequency map")

        self.renew_rng()

        def sample_once() -> str:
            if self.strategy == "random":
                return self.rng.choice(values)
            elif self.strategy == "frequency":
                return self.rng.choices(values, weights=freqs, k=1)[0]
            elif self.strategy == "inverse_frequency":
                inv = [1.0 / f for f in freqs]
                return self.rng.choices(values, weights=inv, k=1)[0]
            else:
                raise ValueError(f"Unsupported sampling strategy: {self.strategy}")

        if avoid_exist_if_possible is None:
            return sample_once()

        if all(v in avoid_exist_if_possible for v in values):
            return (
                sample_once()
            )  # fallback to allow duplicates if all options are exhausted

        while True:
            sampled = sample_once()
            if sampled not in avoid_exist_if_possible:
                return sampled


class RedundantStatementInsert(BaseOperator):
    """
    Modular redundant-code insertion for Java.

    Main knobs:
      - analyzer_mode controls statement pattern:
          def_only / def_use / inc_dec / dec_inc / random
      - type_sampling / name_sampling / init_sampling control how values are picked:
          frequency / inverse_frequency / random
    """

    def __init__(
        self,
        insert_ratio: float = 1.0,
        seed: int = 42,
        analyzer_mode: str = "random",
        type_sampling: str = "random",
        name_sampling: str = "random",
        init_sampling: str = "random",
        stats_path: str | None = None,
        stats_scope: str = "BigCloneBench",
    ):
        super().__init__()
        if not 0.0 < insert_ratio <= 1.0:
            raise ValueError("insert_ratio must be in (0, 1]")
        if analyzer_mode not in SUPPORTED_ANALYZER_MODES:
            raise ValueError(f"Unsupported analyzer_mode: {analyzer_mode}")
        if type_sampling not in SUPPORTED_SAMPLING_MODES:
            raise ValueError(f"Unsupported type_sampling: {type_sampling}")
        if name_sampling not in SUPPORTED_SAMPLING_MODES:
            raise ValueError(f"Unsupported name_sampling: {name_sampling}")
        if init_sampling not in SUPPORTED_SAMPLING_MODES:
            raise ValueError(f"Unsupported init_sampling: {init_sampling}")

        self.insert_ratio = insert_ratio
        self.analyzer_mode = analyzer_mode
        Sampler.reset_shared_seed(seed)

        stats_path = stats_path or str(
            Path(__file__).resolve().parents[2]
            / "data"
            / "variable_frequency_stats.json"
        )
        type_freq, name_freq, init_freq, name_freq_by_type, init_freq_by_type = (
            self._load_frequency_maps(
                Path(stats_path),
                stats_scope=stats_scope,
            )
        )
        numeric_type_freq = {k: v for k, v in type_freq.items() if k in NUMERIC_TYPES}

        self.control_sampler = RandomSampler()
        self.safe_type_sampler = WeightedSampler(type_sampling, type_freq)
        self.numeric_type_sampler = WeightedSampler(type_sampling, numeric_type_freq)
        self.name_sampler_default = WeightedSampler(name_sampling, name_freq)
        self.init_sampler_default = WeightedSampler(init_sampling, init_freq)
        self.name_sampler_by_type = {
            var_type: WeightedSampler(name_sampling, freq_map)
            for var_type, freq_map in name_freq_by_type.items()
        }
        self.init_sampler_by_type = {
            var_type: WeightedSampler(init_sampling, freq_map)
            for var_type, freq_map in init_freq_by_type.items()
        }

    def __call__(self, code: str, k=1) -> str:
        modified_code = code
        for _ in range(k):
            try:
                modified_code = self.operate(modified_code)
            except UnicodeDecodeError:
                pass
        return modified_code

    def operate(self, code: str) -> str:
        code_bytes = bytearray(code.encode("utf-8"))

        java_language = Language(tsjava.language())
        parser = Parser(java_language)
        tree = parser.parse(code_bytes)

        sites = self._collect_sites(tree.root_node)
        if not sites:
            return code

        k = max(1, int(len(sites) * self.insert_ratio))
        chosen = self.control_sampler.sample(sites, min(k, len(sites)))
        chosen.sort(key=lambda s: s["insert_after_byte"], reverse=True)

        for site in chosen:
            stmt_str = self._build_statement(code_bytes, site)
            if stmt_str is None:
                continue
            pos = site["insert_after_byte"]
            indent = site["indent"]
            indented = stmt_str.replace("\n", "\n" + indent)
            snippet = ("\n" + indent + indented).encode("utf-8")
            code_bytes = code_bytes[:pos] + snippet + code_bytes[pos:]

        return code_bytes.decode("utf-8")

    @staticmethod
    def _load_frequency_maps(stats_path: Path, stats_scope: str) -> tuple[
        dict[str, int],
        dict[str, int],
        dict[str, int],
        dict[str, dict[str, int]],
        dict[str, dict[str, int]],
    ]:
        if not stats_path.exists():
            raise FileNotFoundError(f"Statistics file not found: {stats_path}")

        with stats_path.open("r", encoding="utf-8") as f:
            stats = json.load(f)

        if stats_scope == "overall":
            node = stats["overall"]
        else:
            node = stats["datasets"].get(stats_scope)
            if node is None:
                supported = sorted(list(stats.get("datasets", {}).keys()) + ["overall"])
                raise ValueError(
                    f"Unknown stats_scope `{stats_scope}`. Supported: {supported}"
                )

        type_freq = {
            k: int(v)
            for k, v in node["variable_type_frequency"].items()
            if k in SAFE_TYPES
        }
        name_freq = {
            k: int(v)
            for k, v in node["variable_name_frequency"].items()
            if _IDENT_RE.match(k) and k not in JAVA_KEYWORDS
        }
        init_freq = {
            k: int(v)
            for k, v in node["variable_init_value_frequency"].items()
            if k != "<NO_INIT>" and RedundantStatementInsert._is_safe_initializer(k)
        }
        name_freq_by_type: dict[str, dict[str, int]] = {}
        for var_type, freq_map in node.get(
            "variable_name_frequency_by_type", {}
        ).items():
            if var_type not in SAFE_TYPES:
                continue
            filtered = {
                k: int(v)
                for k, v in freq_map.items()
                if _IDENT_RE.match(k) and k not in JAVA_KEYWORDS
            }
            if filtered:
                name_freq_by_type[var_type] = filtered
        init_freq_by_type: dict[str, dict[str, int]] = {}
        for var_type, freq_map in node.get(
            "variable_init_value_frequency_by_type", {}
        ).items():
            if var_type not in SAFE_TYPES:
                continue
            filtered = {
                k: int(v)
                for k, v in freq_map.items()
                if k != "<NO_INIT>" and RedundantStatementInsert._is_safe_initializer(k)
            }
            if filtered:
                init_freq_by_type[var_type] = filtered

        if not type_freq:
            type_freq = {"int": 10, "String": 10, "boolean": 10, "Object": 10}
        if not name_freq:
            name_freq = {"tmp": 1, "count": 1, "value": 1}
        if not init_freq:
            init_freq = {"0": 5, "null": 3, "false": 2}

        return type_freq, name_freq, init_freq, name_freq_by_type, init_freq_by_type

    @staticmethod
    def _is_safe_initializer(value: str) -> bool:
        v = value.strip()
        if v in {"null", "true", "false"}:
            return True
        if _NUMERIC_LITERAL_RE.match(v):
            return True
        if (len(v) >= 2 and v[0] == '"' and v[-1] == '"') or (
            len(v) >= 3 and v[0] == "'" and v[-1] == "'"
        ):
            return True
        return False

    def _collect_sites(self, root):
        sites = []
        self._traverse(root, sites)
        return sites

    def _traverse(self, node, sites):
        if node.type == "block":
            parent = node.parent
            if parent and parent.type in (
                "method_declaration",
                "constructor_declaration",
            ):
                site = self._make_site(node)
                if site is not None:
                    sites.append(site)
        for child in node.children:
            self._traverse(child, sites)

    def _make_site(self, block_node):
        safe_stmts = [
            c for c in block_node.named_children if c.type not in _UNSAFE_AFTER
        ]
        if not safe_stmts:
            return None
        anchor = self.control_sampler.choice(safe_stmts)
        indent = " " * anchor.start_point[1]
        return {
            "insert_after_byte": anchor.end_byte,
            "block_node": block_node,
            "indent": indent,
        }

    def _build_statement(self, source_code: bytes, site: dict) -> str | None:
        if self.analyzer_mode == "random":
            # Randomly pick one of the standard modes and delegate
            chosen_mode = self.control_sampler.choice(
                ["def_only", "def_use", "inc_dec", "dec_inc"]
            )
        else:
            chosen_mode = self.analyzer_mode

        if chosen_mode in {"inc_dec", "dec_inc"}:
            # freq_sequence is already filtered to NUMERIC_TYPES
            java_type = self.numeric_type_sampler.pick()
        else:
            # freq_sequence is already filtered to SAFE_TYPES
            java_type = self.safe_type_sampler.pick()

        name_sampler = self.name_sampler_by_type.get(
            java_type, self.name_sampler_default
        )
        init_sampler = self.init_sampler_by_type.get(
            java_type, self.init_sampler_default
        )

        existing_names = self._collect_identifiers(source_code, site["block_node"])
        sampled_name = name_sampler.pick(avoid_exist_if_possible=existing_names)
        sampled_init = init_sampler.pick()

        safe_name = self._unique_name(sampled_name, existing_names)
        safe_init = self._coerce_initializer_for_type(sampled_init, java_type)

        if chosen_mode == "def_only":
            return f"{java_type} {safe_name} = {safe_init};"
        elif chosen_mode == "def_use":
            return f"{java_type} {safe_name} = {safe_init};\n{safe_name} = {safe_init};"
        elif chosen_mode in {"inc_dec", "dec_inc"}:
            if java_type not in NUMERIC_TYPES:
                return None
            if chosen_mode == "inc_dec":
                num_init = self._coerce_initializer_for_type("0", java_type)
                return f"{java_type} {safe_name} = {num_init};\n{safe_name}++;\n{safe_name}--;"
            else:
                num_init = self._coerce_initializer_for_type("0", java_type)
                return f"{java_type} {safe_name} = {num_init};\n{safe_name}--;\n{safe_name}++;"
        else:
            raise ValueError(f"Unsupported analyzer_mode: {chosen_mode}")

    @staticmethod
    def _coerce_initializer_for_type(initializer: str, java_type: str) -> str:
        v = initializer.strip()
        if java_type == "boolean":
            return v if v in {"true", "false"} else "false"
        if java_type in {"String", "Object"}:
            if v == "null" or (len(v) >= 2 and v[0] == '"' and v[-1] == '"'):
                return v
            return "null"
        if java_type == "char":
            if len(v) >= 3 and v[0] == "'" and v[-1] == "'":
                return v
            return "'a'"
        if java_type == "long":
            if v.endswith(("L", "l")) and _NUMERIC_LITERAL_RE.match(v):
                return v
            if _NUMERIC_LITERAL_RE.match(v):
                return f"{v.rstrip('fFdD') if v else '0'}L"
            return "0L"
        if java_type == "float":
            if v.endswith(("f", "F")) and _NUMERIC_LITERAL_RE.match(v):
                return v
            if _NUMERIC_LITERAL_RE.match(v):
                base = v.rstrip("lLdD")
                return f"{base}f"
            return "0.0f"
        if java_type == "double":
            if _NUMERIC_LITERAL_RE.match(v):
                return v.rstrip("lLfF") or "0.0"
            return "0.0"
        # int / byte / short
        if _NUMERIC_LITERAL_RE.match(v):
            return re.sub(r"[lLfFdD]$", "", v)
        return "0"

    @staticmethod
    def _unique_name(base: str, existing_names: set) -> str:
        if base not in existing_names and base not in JAVA_KEYWORDS:
            return base
        i = 1
        while f"{base}{i}" in existing_names or f"{base}{i}" in JAVA_KEYWORDS:
            i += 1
        return f"{base}{i}"

    def _collect_identifiers(self, source_code: bytes, block_node) -> set:
        names = set()

        def gather(node):
            if node.type == "identifier":
                names.add(source_code[node.start_byte : node.end_byte].decode("utf-8"))
            for child in node.children:
                gather(child)

        gather(block_node)

        ancestor = block_node.parent
        while ancestor:
            if ancestor.type in (
                "method_declaration",
                "constructor_declaration",
                "class_declaration",
            ):
                gather(ancestor)
                break
            ancestor = ancestor.parent

        return names


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_filepath = os.path.join(script_dir, "../tests/TestLoops.java")
    output_filepath = os.path.join(
        script_dir, "../tests/TestLoops_RedundantInsert.java"
    )

    if not os.path.exists(input_filepath):
        print(f"Error: input file '{input_filepath}' not found.")
        sys.exit(1)

    with open(input_filepath, "r") as f:
        original = f.read()

    op = RedundantStatementInsert(
        insert_ratio=1.0,
        seed=42,
        analyzer_mode="random",
        type_sampling="inverse_frequency",
        name_sampling="frequency",
        init_sampling="random",
    )
    perturbed = op(original)

    with open(output_filepath, "b") as f:
        f.write(perturbed)

    print(f"Saved to : {output_filepath}")
