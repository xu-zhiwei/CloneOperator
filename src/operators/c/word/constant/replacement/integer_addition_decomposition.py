"""C11 WC3: IntegerAdditionDecomposition."""
from operators.c.tools.strategy import CStrategy


class IntegerAdditionDecomposition(CStrategy):
    strategy_id = "WC3"
    node_types = {"number_literal"}

    def analyze_site(self, ctx, node):
        if not self.safe_literal(ctx, node):
            return self.reject(ctx, node, "literal_type_or_context_unknown")
        value = ctx.integer(node)
        return [
            self.accept(
                ctx, node, f"({value//2} + {value-value//2})", "same_int_constant"
            )
        ]
