"""O5 - Loop Replacement.

Call ``LoopReplace(mode=...)(code, k=n)`` to convert Java loops. Modes are
``for_to_while``, ``for_to_dowhile``, ``while_to_for``, ``dowhile_to_for``,
and ``random``.
"""

import os
import sys
import random

try:
    from .base_operator import BaseOperator
    from .loop_replace_impl.for_to_while import ForToWhile
    from .loop_replace_impl.for_to_dowhile import ForToDoWhile
    from .loop_replace_impl.while_to_for import WhileToFor
    from .loop_replace_impl.dowhile_to_for import DoWhileToFor
except ImportError:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from base_operator import BaseOperator
    from loop_replace_impl.for_to_while import ForToWhile
    from loop_replace_impl.for_to_dowhile import ForToDoWhile
    from loop_replace_impl.while_to_for import WhileToFor
    from loop_replace_impl.dowhile_to_for import DoWhileToFor


class LoopReplace(BaseOperator):
    def __init__(self, mode="random", seed=42):
        """
        Initialize the loop conversion mode.

        `mode` is `random` or one of `for_to_while`, `for_to_dowhile`,
        `while_to_for`, and `dowhile_to_for`. `seed` makes random selection
        reproducible.
        """
        super().__init__()
        self.seed = seed
        self.mode = mode

        self.operators = {
            "for_to_while": ForToWhile(),
            "for_to_dowhile": ForToDoWhile(),
            "while_to_for": WhileToFor(),
            "dowhile_to_for": DoWhileToFor(),
        }

    def __call__(self, code: str, k=1) -> str:
        modified_code = code
        for _ in range(k):
            selected_mode = self.mode
            if self.mode == "random":
                random.seed(self.seed)  # Set seed for reproducibility
                selected_mode = random.choice(list(self.operators.keys()))
                self.seed += 1  # Increment seed to ensure different random choices in subsequent calls

            operator = self.operators.get(selected_mode)
            if operator:
                modified_code = operator(modified_code)
        return modified_code


if __name__ == "__main__":
    # Force mode to while_to_for for testing
    operator = LoopReplace(mode="while_to_for")

    code = """
    public class Example {
        public void testLoops() {
            // 1. Test While to For
            int count = 0;
            while (count < 10) {
                System.out.println("While: " + count);
                count++;
            }
            
            // 2. Test Do-While to For
            int x = 0;
            do {
                if (x == 5) {
                    x++;
                    continue; 
                }
                System.out.println("Do-While: " + x);
                x++;
            } while (x < 10);
        }
    }
    """

    modified_code = operator(code)
    print("=== Original Code ===")
    print(code)
    print("\n=== Modified Code (while_to_for) ===")
    print(modified_code)

    # Test dowhile_to_for
    operator_dowhile = LoopReplace(mode="dowhile_to_for")
    modified_code_dowhile = operator_dowhile(code)
    print("\n=== Modified Code (dowhile_to_for) ===")
    print(modified_code_dowhile)
