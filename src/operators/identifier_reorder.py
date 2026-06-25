"""O4 - Operand Reordering.

Call ``IdentifierReorder(...)(code, k=n)`` to swap safe commutative operands.
``reorder_ratio`` controls the proportion of eligible expressions to change.
"""

import os
import random
import sys
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

# Ensure we can import from the current directory and parent directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from .base_operator import BaseOperator

COMMUTATIVE_OPERATORS = {"+", "*", "==", "!=", "&", "|", "^"}

# Operand swaps are limited to cases that are likely to preserve Java semantics:
# - String concatenation is skipped because '+' is order-sensitive for strings.
# - Expressions with method calls, assignments, or updates are skipped to avoid
#   changing evaluation order or side effects.
# - Short-circuit operators are not included; floating-point cases are treated
#   conservatively by only swapping simple operands.


class IdentifierReorder(BaseOperator):
    def __init__(self, reorder_ratio: float = 1.0, seed=42):
        super().__init__()
        self.seed = seed

        if not 0.0 <= reorder_ratio <= 1.0:
            raise ValueError("reorder_ratio must be between 0.0 and 1.0")
        self.reorder_ratio = reorder_ratio

        self.JAVA_LANGUAGE = Language(tsjava.language())
        self.parser = Parser()
        if hasattr(self.parser, "set_language"):
            self.parser.set_language(self.JAVA_LANGUAGE)
        else:
            self.parser = Parser(self.JAVA_LANGUAGE)

    def find_nodes_by_type(self, node, node_type):
        nodes = []
        if node.type == node_type:
            nodes.append(node)

        for child in node.children:
            nodes.extend(self.find_nodes_by_type(child, node_type))

        return nodes

    def get_operator(self, binary_node, source):
        op_node = binary_node.child_by_field_name("operator")

        if op_node:
            return source[op_node.start_byte : op_node.end_byte].decode()

        if len(binary_node.children) >= 3:
            return source[
                binary_node.children[1].start_byte : binary_node.children[1].end_byte
            ].decode()

        return None

    def has_side_effect(self, node):
        """
        Checks if a node contains operations that might produce side effects.
        If there are side effects (e.g., method invocations, assignments, increments/decrements, object creations), it is not safe to reorder.
        """
        side_effect_types = {
            "method_invocation",
            "assignment_expression",
            "update_expression",
            "object_creation_expression",
        }

        if node.type in side_effect_types:
            return True

        for child in node.children:
            if self.has_side_effect(child):
                return True

        return False

    def contains_string_literal(self, node):
        """
        Checks if a node contains a string literal.
        Used to avoid reordering string concatenations when encountering the '+' operator.
        """
        if node.type == "string_literal":
            return True

        for child in node.children:
            if self.contains_string_literal(child):
                return True

        return False

    def transform_identifier_reorder(self, source_code: bytes) -> bytes:
        tree = self.parser.parse(source_code)
        root = tree.root_node

        binary_nodes = self.find_nodes_by_type(root, "binary_expression")

        # Replace from back to front to avoid byte offset issues
        for node in reversed(binary_nodes):

            operator = self.get_operator(node, source_code)

            if operator not in COMMUTATIVE_OPERATORS:
                continue

            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")

            if not left or not right:
                continue

            # Special Case 1: Operations with side effects (method calls, assignments, inc/dec, etc.)
            # Side Effects: If operands have side effects, reordering them can change program behavior.
            if self.has_side_effect(left) or self.has_side_effect(right):
                continue

            # Special Case 2: String concatenation
            # String Concatenation: In Java, '+' is used for string concatenation. Reordering changes the result.
            if operator == "+":
                if self.contains_string_literal(left) or self.contains_string_literal(
                    right
                ):
                    continue

            self.seed += 1  # Increment seed for next operation to ensure variability
            random.seed(self.seed)
            if random.random() > self.reorder_ratio:
                continue

            left_code = source_code[left.start_byte : left.end_byte]
            right_code = source_code[right.start_byte : right.end_byte]

            op_code = operator.encode()

            new_expr = right_code + b" " + op_code + b" " + left_code

            start = node.start_byte
            end = node.end_byte

            source_code = source_code[:start] + new_expr + source_code[end:]

        return source_code

    def __call__(self, code: str, k=1) -> str:
        modified_code = code
        for _ in range(k):
            modified_code = modified_code.encode("utf-8")
            modified_code = self.transform_identifier_reorder(modified_code)
            modified_code = modified_code.decode("utf-8")
        return modified_code


def transform_identifier_reorder(source_code: bytes, reorder_ratio: float = 1.0) -> bytes:
    """
    Backward-compatible function wrapper for script-style usage.
    Prefer using IdentifierReorder as an operator class.
    """
    return IdentifierReorder(reorder_ratio=reorder_ratio).transform_identifier_reorder(
        source_code
    )


if __name__ == "__main__":
    operator = IdentifierReorder()

    script_dir = os.path.dirname(os.path.abspath(__file__))

    input_file = os.path.join(script_dir, "TestIdentifierReorder.java")
    output_file = os.path.join(script_dir, "TestIdentifierReorder_Perturbed.java")

    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)

    print(f"Reading file: {input_file}")

    with open(input_file, "rb") as f:
        source = f.read()

    print("Applying identifier reorder transformation...")

    result = operator.transform_identifier_reorder(source)

    with open(output_file, "wb") as f:
        f.write(result)

    print(f"Transformation finished. Output saved to: {output_file}")
