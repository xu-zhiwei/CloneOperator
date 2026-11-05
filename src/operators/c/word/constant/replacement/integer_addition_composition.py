"""c WC6: IntegerAdditionComposition. Checked directional transformation."""
from operators.c.tools.strategy import CStrategy




class IntegerAdditionComposition(CStrategy):
    strategy_id = "WC6"
    node_types = {"binary_expression"}

    def analyze_site(self, ctx, node):
        if ctx.op(node) != "+":
            return []
        if not self.rvalue(ctx, node) or not all(self.safe_literal(ctx, node.child_by_field_name(f)) for f in ("left", "right")):
            return self.reject(ctx, node, "not_literal_rvalue")
        left, right = ctx.integer(node.child_by_field_name("left")), ctx.integer(node.child_by_field_name("right"))
        if left is None or right is None:
            return self.reject(ctx, node, "not_guaranteed_int_literals")
        value = left + right
        if not -32767 <= value <= 32767:
            return self.reject(ctx, node, "constant_result_out_of_range")
        replacement = f"({value})"
        return [self.accept(ctx, node, replacement, "typed_constant_composition")]
