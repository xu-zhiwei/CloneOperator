"""WC2: ConstantNeutralTermRemoval."""
from operators.base.candidate import AnalyzedStrategy


class ConstantNeutralTermRemoval(AnalyzedStrategy):
    strategy_id = "WC2"
    node_types = {"binary_expression"}

    def analyze_site(self, ctx, node):
        left, right = (
            node.child_by_field_name("left"),
            node.child_by_field_name("right"),
        )
        a, b = ctx.integer(left), ctx.integer(right)
        op = ctx.op(node)
        if op not in {"+", "-", "*", "^"}:
            return []
        if a is None or b is None or a[1] != b[1]:
            return self.reject(ctx, node, "constant_identity_type_mismatch")
        if b[0] == (1 if op == "*" else 0):
            return [self.accept(ctx, node, ctx.text(left), "remove_right_identity")]
        if op in {"+", "*", "^"} and a[0] == (1 if op == "*" else 0):
            return [self.accept(ctx, node, ctx.text(right), "remove_left_identity")]
        return self.reject(ctx, node, "not_an_integer_identity")
