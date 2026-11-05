"""c WC8: BooleanNegationConstantReduction. Checked directional transformation."""
from operators.c.tools.strategy import CStrategy
from operators.tools.source import unwrap



class BooleanNegationConstantReduction(CStrategy):
    strategy_id = "WC8"
    node_types = {"unary_expression"}

    def analyze_site(self, ctx, node):
        if ctx.op(node) != "!":
            return []
        argument = unwrap(node.child_by_field_name("argument"))
        value = ctx.integer(argument)
        if value not in {0, 1} or not self.rvalue(ctx, node):
            return self.reject(ctx, node, "not_negated_int_truth_literal")
        replacement = str(int(not value))
        return [self.accept(ctx, node, replacement, "logical_constant_reduction")]
