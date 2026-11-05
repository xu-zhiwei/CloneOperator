"""C11 WC1: ConstantNeutralTermInsertion."""
from operators.c.tools.strategy import CStrategy


class ConstantNeutralTermInsertion(CStrategy):
    strategy_id = "WC1"
    node_types = {"number_literal"}

    def analyze_site(self, ctx, node):
        if not self.safe_literal(ctx, node):
            return self.reject(ctx, node, "literal_type_or_context_unknown")
        value = ctx.integer(node)
        return [self.accept(ctx, node, f"({value} + 0)", "same_int_constant")]
