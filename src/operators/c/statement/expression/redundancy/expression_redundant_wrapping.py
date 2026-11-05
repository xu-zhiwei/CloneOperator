"""C11 SE2: ExpressionRedundantWrapping."""
from operators.c.tools.strategy import CStrategy


class ExpressionRedundantWrapping(CStrategy):
    strategy_id = "SE2"
    node_types = {"binary_expression", "identifier"}

    def analyze_site(self, ctx, node):
        if (
            not self.rvalue(ctx, node)
            or not ctx.pure(node)
            or ctx.integer(node) is not None
        ):
            return self.reject(ctx, node, "not_pure_int_rvalue")
        return [
            self.accept(ctx, node, f"(({ctx.text(node)}) + 0)", "int_neutral_wrapping")
        ]
