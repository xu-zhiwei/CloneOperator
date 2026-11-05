"""C11 WC2: ConstantNeutralTermRemoval."""
from operators.c.tools.strategy import CStrategy


class ConstantNeutralTermRemoval(CStrategy):
    strategy_id = "WC2"
    node_types = {"binary_expression"}

    def analyze_site(self, ctx, node):
        l, r = node.child_by_field_name("left"), node.child_by_field_name("right")
        if (
            ctx.op(node) not in {"+", "-"}
            or ctx.integer(l) is None
            or ctx.integer(r) != 0
            or not self.rvalue(ctx, node)
        ):
            return self.reject(ctx, node, "not_redundant_int_constant")
        return [self.accept(ctx, node, ctx.text(l), "remove_constant_neutral_term")]
