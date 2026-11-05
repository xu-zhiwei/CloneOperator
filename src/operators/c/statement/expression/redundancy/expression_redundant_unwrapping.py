"""C11 SE3: ExpressionRedundantUnwrapping."""
from operators.c.tools.strategy import CStrategy


class ExpressionRedundantUnwrapping(CStrategy):
    strategy_id = "SE3"
    node_types = {"binary_expression"}

    def analyze_site(self, ctx, node):
        l, r = node.child_by_field_name("left"), node.child_by_field_name("right")
        if (
            ctx.op(node) != "+"
            or ctx.integer(r) != 0
            or ctx.integer(l) is not None
            or not ctx.pure(l)
            or not self.rvalue(ctx, node)
        ):
            return self.reject(ctx, node, "not_wrapped_int_expression")
        return [self.accept(ctx, node, f"({ctx.text(l)})", "int_neutral_unwrapping")]
