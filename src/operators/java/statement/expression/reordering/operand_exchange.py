"""SE1: OperandExchange."""
from operators.java.statement.expression.tools import BinaryExpressionStrategy


class OperandExchange(BinaryExpressionStrategy):
    strategy_id = "SE1"

    def __init__(self, operators=("+", "*", "&", "|", "^", "==", "!="), **kwargs):
        super().__init__(**kwargs)
        self.operators = self.validate_modes(
            operators, {"+", "*", "&", "|", "^", "==", "!="}
        )

    def analyze_site(self, ctx, node):
        if ctx.op(node) not in self.operators:
            return []
        pair = self.pure_operands(ctx, node)
        if pair is None:
            return []
        a, b = pair
        if ctx.text(a) == ctx.text(b):
            return self.reject(ctx, node, "identical_operands")
        return [
            self.accept(
                ctx,
                node,
                f"(({ctx.text(b)}) {ctx.op(node)} ({ctx.text(a)}))",
                "operand_exchange",
            )
        ]
