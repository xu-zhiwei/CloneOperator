"""O3 - Redundant Constant Insertion.

Call ``RedundantConstantInsert(...)(code, k=n)`` to add redundant expressions
around Java literals. ``factor`` controls the numeric identity expressions.
"""

import re

import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from .base_operator import BaseOperator


class RedundantConstantInsert(BaseOperator):
    SUPPORTED_LITERAL_TYPES = {
        "decimal_integer_literal",
        "decimal_floating_point_literal",
        "string_literal",
        "true",
        "false",
    }

    def __init__(self, token_vocab=None, seed=42, factor: int = 1):
        super().__init__()
        if token_vocab is None:
            self._load_token_vocab()
        else:
            self.token_vocab = set(token_vocab)

        self._rng = __import__("random").Random(seed)
        if not isinstance(factor, int) or factor == 0:
            raise ValueError("factor must be a non-zero integer")
        self.factor = factor
        self.last_constants = []
        self.last_recommendations = []

    def __call__(self, code, k=1):
        modified_code = code
        for _ in range(k):
            modified_code = self.operate(modified_code)[0]
        return modified_code

    def operate(self, code):
        input_is_bytes = isinstance(code, (bytes, bytearray))
        code_bytes = bytearray(code if input_is_bytes else code.encode("utf-8"))

        tree = self._parse_code(code_bytes)
        constants = self.identify_constants(tree, code_bytes)
        recommendations = self.recommend_replacements(constants)
        updated_code = self.apply_replacements(code_bytes, recommendations)

        if input_is_bytes:
            return bytes(updated_code), recommendations
        return updated_code.decode("utf-8"), recommendations

    def _parse_code(self, code_bytes):
        parser = Parser(Language(tsjava.language()))
        return parser.parse(bytes(code_bytes))

    def identify_constants(self, tree, code_bytes):
        constants = []

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
        factor = self.factor
        # Preserve value by adding 0 or multiplying 1-like expression.
        return self._pick_random_supported(
            [
                f"({literal_text} + 0)",
                f"(0 + {literal_text})",
                f"({literal_text} + (1 - 1))",
                f"((1 - 1) + {literal_text})",
                f"({literal_text} * 1)",
                f"(1 * {literal_text})",
                f"({literal_text} * (1 / 1))",
                f"((1 / 1) * {literal_text})",
                f"({literal_text} + ({factor} - {factor}))",
                f"(({factor} - {factor}) + {literal_text})",
                f"(({literal_text} * {factor}) / {factor})",
                f"(({factor} * {literal_text}) / {factor})",
            ]
        )

    def _recommend_string_insertion(self, literal_text):
        if not re.fullmatch(r'"([^"\\]|\\.)*"', literal_text):
            return None

        return self._pick_random_supported(
            [f'({literal_text} + "")', f'("" + {literal_text})']
        )

    def _recommend_boolean_insertion(self, value):
        if value:
            return self._pick_random_supported(["(true || false)", "(false || true)", "(true && true)"])
        return self._pick_random_supported(["(false && true)", "(true && false)", "(false || false)"])

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
            r"\d+\.\d+|\d+|[A-Za-z_][A-Za-z_0-9]*|==|!=|<=|>=|&&|\|\||\S",
            candidate,
        )

    def _load_token_vocab(self):
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained("microsoft/codebert-base")
        self.token_vocab = set(tokenizer.get_vocab().keys())


if __name__ == "__main__":
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    TEST_CODE = """
public class RedundantConstantInsertTest {
	static int a = 5;
	static double b = 3.14;
	static String c = "error";
	static boolean d = true;
	static boolean e = false;
}
""".strip()

    def _show(operator, code):
        new_code = operator(code)
        print("\nOriginal:")
        print(code)
        print("\nAfter insertion:")
        print(new_code)
        print("\nDetected constants:")
        for c in operator.last_constants:
            print(f"  {c['type']:35s} {c['text']!r}")
        print("\nApplied insertions:")
        for r in operator.last_recommendations:
            print(f"  {r['text']!r:16s}  =>  {r['replacement']!r}")

    op = RedundantConstantInsert()
    _show(op, TEST_CODE)
