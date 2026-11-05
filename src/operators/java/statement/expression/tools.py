"""Shared analysis and construction helpers for this target."""
from operators.base.candidate import AnalyzedStrategy


class BinaryExpressionStrategy(AnalyzedStrategy):
    node_types = {"binary_expression"}

    def operands(self, ctx, node):
        return node.child_by_field_name("left"), node.child_by_field_name("right")

    def pure_operands(self, ctx, node):
        a, b = self.operands(ctx, node)
        if not ctx.pure(a) or not ctx.pure(b):
            reasons = ctx.effects(a).reasons | ctx.effects(b).reasons
            ctx.reject(
                node,
                "unsafe_operands",
                effects=sorted(reasons),
                types=[ctx.expression_type(a), ctx.expression_type(b)],
            )
            return None
        return a, b
