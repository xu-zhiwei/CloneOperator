"""java SE9: DeMorganExpansion. Checked directional transformation."""
from operators.base.candidate import AnalyzedStrategy
from operators.tools.source import unwrap
from operators.java.analysis.rewriting import boolean


class DeMorganExpansion(AnalyzedStrategy):
    strategy_id = "SE9"
    node_types = {"unary_expression"}

    def analyze_site(self, ctx, node):
        if ctx.op(node) != "!":
            return []
        expr = unwrap(node.named_children[-1])
        if expr.type != "binary_expression" or ctx.op(expr) not in {"&&", "||"} or not boolean(ctx, node):
            return self.reject(ctx, node, "not_confirmed_negated_logical_expression")
        a, b = expr.child_by_field_name("left"), expr.child_by_field_name("right")
        op = "||" if ctx.op(expr) == "&&" else "&&"
        replacement = f"(!({ctx.text(a)}) {op} !({ctx.text(b)}))"
        return [self.accept(ctx, node, replacement, "ordered_short_circuit_demorgan")]
