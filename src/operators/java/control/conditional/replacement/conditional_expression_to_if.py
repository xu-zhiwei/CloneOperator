"""java CC11: ConditionalExpressionToIf. Checked directional transformation."""
from operators.base.candidate import AnalyzedStrategy
from operators.tools.source import unwrap
from operators.java.analysis.rewriting import boolean, writable


class ConditionalExpressionToIf(AnalyzedStrategy):
    strategy_id = "CC11"
    node_types = {"expression_statement"}

    def analyze_site(self, ctx, node):
        if len(node.named_children) != 1:
            return []
        expr = node.named_children[0]
        if expr.type != "assignment_expression" or ctx.op(expr) != "=":
            return []
        s = writable(ctx, expr.child_by_field_name("left"))
        rhs = unwrap(expr.child_by_field_name("right"))
        if not s or rhs.type not in {"ternary_expression", "conditional_expression"}:
            return self.reject(ctx, node, "not_local_conditional_assignment")
        cond, a, b = (rhs.child_by_field_name(field) for field in ("condition", "consequence", "alternative"))
        if not all(x is not None for x in (cond, a, b)) or not boolean(ctx, cond):
            return self.reject(ctx, node, "unknown_conditional_types")
        if not ctx.pure(a, {s.java_type}) or not ctx.pure(b, {s.java_type}) or ctx.expression_type(a) != s.java_type or ctx.expression_type(b) != s.java_type:
            return self.reject(ctx, node, "conditional_branch_type_conversion")
        return [self.accept(ctx, node, f"if ({ctx.text(cond)}) {{ {s.name} = {ctx.text(a)}; }} else {{ {s.name} = {ctx.text(b)}; }}", "conditional_assignment_to_if")]
