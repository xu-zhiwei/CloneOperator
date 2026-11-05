"""java WC8: BooleanNegationConstantReduction. Checked directional transformation."""
from operators.base.candidate import AnalyzedStrategy
from operators.tools.source import unwrap



class BooleanNegationConstantReduction(AnalyzedStrategy):
    strategy_id = "WC8"
    node_types = {"unary_expression"}

    def analyze_site(self, ctx, node):
        if ctx.op(node) != "!":
            return []
        argument = unwrap(node.named_children[-1])
        if argument.type not in {"true", "false"}:
            return self.reject(ctx, node, "not_negated_boolean_literal")
        replacement = "false" if argument.type == "true" else "true"
        return [self.accept(ctx, node, replacement, "logical_constant_reduction")]
