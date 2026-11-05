"""C11 WC5: IntegerSubtractionRepresentation."""
from operators.c.tools.strategy import CStrategy


class IntegerSubtractionRepresentation(CStrategy):
    strategy_id = "WC5"
    node_types = {"number_literal"}

    def analyze_site(self, ctx, node):
        if not self.safe_literal(ctx, node):
            return self.reject(ctx, node, "literal_type_or_context_unknown")
        value = ctx.integer(node)
        return [
            self.accept(
                ctx,
                node,
                f"({value+1} - 1)" if value < 32767 else f"({value-1} - (-1))",
                "same_int_constant",
            )
        ]
