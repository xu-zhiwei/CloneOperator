"""C11 WC4: BooleanNegationReplacement."""
from operators.c.tools.strategy import CStrategy


class BooleanNegationReplacement(CStrategy):
    strategy_id = "WC4"
    node_types = {"number_literal", "unary_expression"}

    def analyze_site(self, ctx, node):
        value = ctx.integer(node)
        if (
            node.type == "number_literal"
            and value in {0, 1}
            and self.safe_literal(ctx, node)
        ):
            return [
                self.accept(
                    ctx, node, "(!1)" if value == 0 else "(!0)", "int_logical_constant"
                )
            ]
        return self.reject(ctx, node, "not_confirmed_int_truth_value")
