"""c CC12: IfToConditionalExpression. Checked directional transformation."""
from operators.c.tools.strategy import CStrategy

from operators.c.analysis.rewriting import boolean, simple_assignment


class IfToConditionalExpression(CStrategy):
    strategy_id = "CC12"
    node_types = {"if_statement"}

    def analyze_site(self, ctx, node):
        if not self.function_safe(ctx, node):
            return self.reject(ctx, node, "unsupported_function_control")
        other = ctx.alternative(node)
        cond = node.child_by_field_name("condition")
        if other is None or not boolean(ctx, cond):
            return self.reject(ctx, node, "missing_else_or_unknown_condition")
        a, b = simple_assignment(ctx, node.child_by_field_name("consequence")), simple_assignment(ctx, other)
        if not a or not b or a[0] is not b[0]:
            return self.reject(ctx, node, "branches_not_single_same_target_assignments")
        s = a[0]
        return [self.accept(ctx, node, f"{s.name} = ({ctx.text(cond)}) ? ({ctx.text(a[1])}) : ({ctx.text(b[1])});", "if_to_conditional_assignment")]
