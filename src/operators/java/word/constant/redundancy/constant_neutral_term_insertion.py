"""WC1: ConstantNeutralTermInsertion."""
from operators.java.word.constant.tools import IntegerLiteralStrategy


class ConstantNeutralTermInsertion(IntegerLiteralStrategy):
    strategy_id = "WC1"

    def __init__(self, modes=("add_zero", "subtract_zero", "multiply_one"), **kwargs):
        super().__init__(**kwargs)
        self.modes = self.validate_modes(
            modes, {"add_zero", "subtract_zero", "multiply_one", "xor_zero"}
        )

    def analyze_site(self, ctx, node):
        literal = self.literal(ctx, node)
        if literal is None:
            return []
        suffix = literal[1]
        choices = {
            "add_zero": ("+", 0),
            "subtract_zero": ("-", 0),
            "multiply_one": ("*", 1),
            "xor_zero": ("^", 0),
        }
        return [
            self.accept(
                ctx,
                node,
                f"({ctx.text(node)} {choices[m][0]} {choices[m][1]}{suffix})",
                m,
            )
            for m in self.modes
        ]
