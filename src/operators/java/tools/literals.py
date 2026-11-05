"""Typed literal discovery, vocabulary filtering and replacement candidates."""
import re
from operators.java.base.construction import ConstructionBase


class LiteralCandidates(ConstructionBase):
    SUPPORTED_LITERAL_TYPES = {
        "decimal_integer_literal",
        "decimal_floating_point_literal",
        "string_literal",
        "character_literal",
        "true",
        "false",
        "null_literal",
    }

    def __init__(
        self,
        token_vocab=None,
        max_numeric_depth=4,
        max_numeric_atoms=12,
        max_string_candidates=32,
    ):
        super().__init__()
        if token_vocab is None:
            self._load_token_vocab()
        else:
            self.token_vocab = set(token_vocab)

        self.max_numeric_depth = max_numeric_depth
        self.max_numeric_atoms = max_numeric_atoms
        self.max_string_candidates = max_string_candidates

        self.last_constants = []
        self.last_recommendations = []

    def identify_constants(self, tree, code_bytes):
        constants = []
        from operators.java.analysis.context import lexing_supported
        if tree.root_node.has_error or not lexing_supported(bytes(code_bytes)):
            return constants

        def traverse(node):
            if node.type in self.SUPPORTED_LITERAL_TYPES:
                literal_text = code_bytes[node.start_byte : node.end_byte].decode(
                    "utf-8"
                )
                constants.append(
                    {
                        "type": node.type,
                        "text": literal_text,
                        "start_byte": node.start_byte,
                        "end_byte": node.end_byte,
                        "parent_type": node.parent.type if node.parent else None,
                    }
                )

            for child in node.children:
                traverse(child)

        traverse(tree.root_node)
        self.last_constants = constants
        return constants

    def recommend_replacements(self, constants):
        recommendations = []
        cached_recommendations = {}

        for constant in constants:
            cache_key = (constant["type"], constant["text"], constant["parent_type"])
            if cache_key not in cached_recommendations:
                cached_recommendations[cache_key] = self._recommend_single_replacement(
                    constant
                )

            replacement = cached_recommendations[cache_key]
            if replacement is None:
                continue

            recommendations.append({**constant, "replacement": replacement})

        self.last_recommendations = recommendations
        return recommendations

    def apply_replacements(self, code_bytes, recommendations):
        for item in sorted(
            recommendations, key=lambda value: value["start_byte"], reverse=True
        ):
            code_bytes[item["start_byte"] : item["end_byte"]] = item[
                "replacement"
            ].encode("utf-8")
        return code_bytes

    def _recommend_single_replacement(self, constant):
        literal_type = constant["type"]
        if literal_type == "decimal_integer_literal":
            return self._recommend_numeric_replacement(constant)
        if literal_type == "true":
            return self._recommend_boolean_replacement(True)
        if literal_type == "false":
            return self._recommend_boolean_replacement(False)
        return None

    def _recommend_numeric_replacement(self, constant):
        match = re.fullmatch(r"([1-9][0-9_]*)([lL]?)", constant["text"])
        if match is None:
            return None
        value = int(match.group(1).replace("_", ""))
        suffix = "L" if match.group(2) else ""
        maximum = (1 << (63 if suffix else 31)) - 1
        # Reject special minimum-value magnitudes and keep every intermediate in range.
        if not 2 <= value <= maximum:
            return None
        left = value // 2
        candidate = f"({left}{suffix} + {value - left}{suffix})"
        return self._pick_first_supported([candidate])

    def _recommend_boolean_replacement(self, value):
        if value:
            return self._pick_first_supported(["(!false)"])
        return self._pick_first_supported(["(!true)"])

    def _pick_first_supported(self, candidates, is_string_literal=False):
        for candidate in candidates:
            if candidate is None:
                continue
            if self._is_supported_candidate(
                candidate, is_string_literal=is_string_literal
            ):
                return candidate
        return None

    def _is_supported_candidate(self, candidate, is_string_literal=False):
        if not self.token_vocab:
            return True

        if is_string_literal:
            inner_text = candidate[1:-1]
            return inner_text in self.token_vocab

        for token in self._tokenize_candidate(candidate):
            if token not in self.token_vocab:
                return False
        return True

    def _tokenize_candidate(self, candidate):
        return re.findall(
            r"\d+\.\d+|\d+|[A-Za-z_][A-Za-z_0-9]*|==|!=|<=|>=|&&|\|\||\S", candidate
        )

    def _load_token_vocab(self):
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained("microsoft/codebert-base")
        self.token_vocab = set(tokenizer.get_vocab().keys())


class NeutralLiteralCandidates(LiteralCandidates):
    def __init__(self, token_vocab=None, seed=42, factor=1):
        super().__init__(token_vocab=token_vocab)
        from random import Random

        self._rng = Random(seed)
        if not isinstance(factor, int) or factor == 0:
            raise ValueError("factor must be a non-zero integer")
        self.factor = factor

    def _recommend_single_replacement(self, constant):
        literal_type = constant["type"]
        literal_text = constant["text"]

        if literal_type in {
            "decimal_integer_literal",
            "decimal_floating_point_literal",
        }:
            return self._recommend_numeric_insertion(literal_text)
        if literal_type == "string_literal":
            return self._recommend_string_insertion(literal_text)
        if literal_type == "true":
            return self._recommend_boolean_insertion(True)
        if literal_type == "false":
            return self._recommend_boolean_insertion(False)
        return None

    def _recommend_numeric_insertion(self, literal_text):
        match = re.fullmatch(r"(0|[1-9][0-9_]*)([lL]?)", literal_text)
        if match is None:
            return None
        value = int(match.group(1).replace("_", ""))
        suffix = "L" if match.group(2) else ""
        if value > (2**63-1 if suffix else 2**31-1):
            return None
        # Multiplication followed by division is not an identity under Java
        # overflow. Floating point zero/one identities also need signed-zero
        # and rounding analysis, so the historical entry uses this typed subset.
        return self._pick_random_supported([
            f"({literal_text} + 0{suffix})",
            f"(0{suffix} + {literal_text})",
            f"({literal_text} - 0{suffix})",
            f"({literal_text} * 1{suffix})",
            f"(1{suffix} * {literal_text})",
        ])

    def _recommend_string_insertion(self, literal_text):
        if not re.fullmatch(r'"([^"\\]|\\.)*"', literal_text):
            return None

        return self._pick_random_supported(
            [f'({literal_text} + "")', f'("" + {literal_text})']
        )

    def _recommend_boolean_insertion(self, value):
        if value:
            return self._pick_random_supported(
                ["(true || false)", "(false || true)", "(true && true)"]
            )
        return self._pick_random_supported(
            ["(false && true)", "(true && false)", "(false || false)"]
        )

    def _pick_random_supported(self, candidates):
        supported = [
            c for c in candidates if c is not None and self._is_supported_candidate(c)
        ]
        if not supported:
            return None
        return self._rng.choice(supported)

    def _pick_first_supported(self, candidates):
        for candidate in candidates:
            if candidate is None:
                continue
            if self._is_supported_candidate(candidate):
                return candidate
        return None

    def _is_supported_candidate(self, candidate):
        if not self.token_vocab:
            return True

        for token in self._tokenize_candidate(candidate):
            if token not in self.token_vocab:
                return False
        return True

    def _tokenize_candidate(self, candidate):
        return re.findall(
            r"\d+\.\d+|\d+|[A-Za-z_][A-Za-z_0-9]*|==|!=|<=|>=|&&|\|\||\S", candidate,
        )


def select_per_statement(tree, constants, rng):
    """Choose at most one literal from each containing statement."""
    from operators.tools.source import walk

    by_range = {(n.start_byte, n.end_byte): n for n in walk(tree.root_node)}
    groups = {}
    for constant in constants:
        node = by_range.get((constant["start_byte"], constant["end_byte"]))
        while (
            node is not None
            and not node.type.endswith("statement")
            and node.type != "local_variable_declaration"
        ):
            node = node.parent
        key = (
            (node.start_byte, node.end_byte)
            if node
            else (constant["start_byte"], constant["end_byte"])
        )
        groups.setdefault(key, []).append(constant)
    return [rng.choice(values) for values in groups.values()]
