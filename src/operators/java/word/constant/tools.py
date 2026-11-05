"""Shared analysis and construction helpers for this target."""
from operators.base.candidate import AnalyzedStrategy


class IntegerLiteralStrategy(AnalyzedStrategy):
    node_types = {"decimal_integer_literal", "unary_expression"}

    def identify_sites(self, ctx):
        for node in super().identify_sites(ctx):
            if (
                node.type == "decimal_integer_literal"
                and node.parent.type == "unary_expression"
            ):
                continue
            if node.type == "unary_expression" and ctx.integer(node) is None:
                continue
            yield node

    def literal(self, ctx, node):
        result = ctx.integer(node)
        if result is None:
            ctx.reject(node, "unsupported_integer_literal")
        return result
