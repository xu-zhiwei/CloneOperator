"""java SE10: DeMorganContraction. Checked directional transformation."""
from operators.base.candidate import AnalyzedStrategy
from operators.tools.source import unwrap
from operators.java.analysis.rewriting import boolean


class DeMorganContraction(AnalyzedStrategy):
    strategy_id = "SE10"
    node_types = {"binary_expression"}

    def analyze_site(self, ctx, node):
        if ctx.op(node) not in {"&&", "||"} or not boolean(ctx, node):
            return []
        a, b = unwrap(node.child_by_field_name("left")), unwrap(node.child_by_field_name("right"))
        if a.type != "unary_expression" or b.type != "unary_expression" or ctx.op(a) != "!" or ctx.op(b) != "!":
            return self.reject(ctx, node, "both_operands_must_be_negated")
        a, b = a.named_children[-1], b.named_children[-1]
        op = "||" if ctx.op(node) == "&&" else "&&"
        replacement = f"!(({ctx.text(a)}) {op} ({ctx.text(b)}))"
        return [self.accept(ctx, node, replacement, "ordered_short_circuit_demorgan")]
