"""java WC6: IntegerAdditionComposition. Checked directional transformation."""
from operators.base.candidate import AnalyzedStrategy




class IntegerAdditionComposition(AnalyzedStrategy):
    strategy_id = "WC6"
    node_types = {"binary_expression"}

    def analyze_site(self, ctx, node):
        if ctx.op(node) != "+":
            return []
        left, right = ctx.integer(node.child_by_field_name("left")), ctx.integer(node.child_by_field_name("right"))
        if left is None or right is None or left[1] != right[1]:
            return self.reject(ctx, node, "literal_types_not_identical")
        value = left[0] + right[0]
        suffix = left[1]
        bits = 64 if suffix else 32
        if not -(2**(bits-1)) <= value < 2**(bits-1):
            return self.reject(ctx, node, "constant_result_out_of_range")
        replacement = f"({value}{suffix})"
        return [self.accept(ctx, node, replacement, "typed_constant_composition")]
