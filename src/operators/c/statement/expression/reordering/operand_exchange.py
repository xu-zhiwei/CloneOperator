"""C11 SE1: OperandExchange."""
from operators.c.tools.strategy import CStrategy


class OperandExchange(CStrategy):
    strategy_id = "SE1"
    node_types = {"binary_expression"}

    def analyze_site(self, ctx, node):
        op = ctx.op(node)
        l, r = node.child_by_field_name("left"), node.child_by_field_name("right")
        if (
            op not in {"+", "*", "&", "|", "^", "==", "!="}
            or not ctx.pure(node)
            or ctx.text(l) == ctx.text(r)
        ):
            return self.reject(ctx, node, "noncommutative_or_effectful_expression")
        return [
            self.accept(
                ctx,
                node,
                f"(({ctx.text(r)}) {op} ({ctx.text(l)}))",
                "pure_operand_exchange",
            )
        ]
