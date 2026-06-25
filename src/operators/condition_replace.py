"""O6 - Condition Replacement.

Call ``ConditionReplace(mode=...)(code, k=n)`` to convert between if/else and
switch statements. Modes are ``if_to_switch_*`` and ``switch_to_if_*``, with
``nesting`` or ``cloning`` in place of ``*``; ``random`` is also supported.
"""

import sys
import os
import random

from tree_sitter import Language, Parser
import tree_sitter_java as tsjava

try:
    from .base_operator import BaseOperator
    from .condition_replace_impl.if_to_switch import IfToSwitch
    from .condition_replace_impl.switch_to_if import SwitchToIf
except ImportError:
    # Script-mode fallback (e.g. running from src/run_condition_tests.py)
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from base_operator import BaseOperator
    from condition_replace_impl.if_to_switch import IfToSwitch
    from condition_replace_impl.switch_to_if import SwitchToIf


class ConditionReplace(BaseOperator):
    def __init__(self, mode="random", seed=42, min_case_count=1):
        """
        Initialize the condition conversion mode.

        `mode` is `random`, `if_to_switch_{nesting,cloning}`, or
        `switch_to_if_{nesting,cloning}`. `min_case_count` filters small
        if-to-switch candidates, and `seed` makes random selection reproducible.
        """
        super().__init__()
        self.seed = seed
        self.mode = mode
        self.parser = Parser(Language(tsjava.language()))

        self.operators = {
            "if_to_switch_nesting": IfToSwitch(
                multi_case_strategy="nesting", min_case_count=min_case_count
            ),
            "if_to_switch_cloning": IfToSwitch(
                multi_case_strategy="cloning", min_case_count=min_case_count
            ),
            "switch_to_if_nesting": SwitchToIf(fallthrough_strategy="nesting"),
            "switch_to_if_cloning": SwitchToIf(fallthrough_strategy="cloning"),
        }

    def __call__(self, code: str, k=1) -> str:
        modified_code = code
        for _ in range(k):
            selected_mode = self.mode
            if self.mode == "random":
                random.seed(self.seed)  # Set seed for reproducibility
                availabel_modes = self._get_avaiable_modes(code)
                if not availabel_modes:
                    continue
                selected_mode = random.choice(availabel_modes)
                self.seed += 1  # Increment seed to ensure different random choices in subsequent calls

            operator = self.operators.get(selected_mode)
            if operator:
                modified_code = operator(modified_code)
        return modified_code

    def _get_avaiable_modes(self, code):
        modes = []
        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)

        has_if = False
        has_switch = False

        def traverse(node):
            nonlocal has_if, has_switch
            if has_if and has_switch:
                return

            if node.type == "if_statement":
                has_if = True
            elif node.type in {"switch_expression", "switch_statement"}:
                has_switch = True

            for child in node.children:
                traverse(child)

        traverse(tree.root_node)

        if has_if:
            modes.append("if_to_switch_nesting")
            modes.append("if_to_switch_cloning")
        if has_switch:
            modes.append("switch_to_if_nesting")
            modes.append("switch_to_if_cloning")
        return modes


if __name__ == "__main__":
    # Test if_to_switch
    operator = ConditionReplace(mode="if_to_switch_cloning")

    code = """
    public class Example {
        public void testConditions(int x) {
            if (x == 1) {
                System.out.println("One");
            } else if (x == 2 || x == 3) {
                System.out.println("Two or Three");
            } else {
                System.out.println("Other");
            }
        }
    }
    """

    modified_code = operator(code)
    print("=== Original Code ===")
    print(code)
    print("\n=== Modified Code (if_to_switch_cloning) ===")
    print(modified_code)

    # Test switch_to_if
    operator = ConditionReplace(mode="switch_to_if_nesting")
    code2 = """
    public class Example {
        public void testConditions(int x) {
            switch (x) {
                case 1:
                    System.out.println("One");
                    break;
                case 2:
                case 3:
                    System.out.println("Two or Three");
                    break;
                default:
                    System.out.println("Other");
                    break;
            }
        }
    }
    """
    modified_code2 = operator(code2)
    print("\n=== Original Code 2 ===")
    print(code2)
    print("\n=== Modified Code (switch_to_if_nesting) ===")
    print(modified_code2)
