"""SE4: RelationalExpressionRewriting."""
from operators.java.statement.expression.tools import BinaryExpressionStrategy


class RelationalExpressionRewriting(BinaryExpressionStrategy):
    strategy_id = "SE4"
    RELATIONS = {"<": ">", ">": "<", "<=": ">=", ">=": "<=", "==": "==", "!=": "!="}

    def analyze_site(self, ctx, node):
        op = ctx.op(node)
        if op not in self.RELATIONS:
            return []
        pair = self.pure_operands(ctx, node)
        if pair is None:
            return []
        a, b = pair
        return [
            self.accept(
                ctx,
                node,
                f"(({ctx.text(b)}) {self.RELATIONS[op]} ({ctx.text(a)}))",
                "reverse_relation",
                operator=op,
            )
        ]
