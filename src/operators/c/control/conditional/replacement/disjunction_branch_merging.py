"""c CC14: DisjunctionBranchMerging. Checked directional transformation."""
from operators.c.tools.strategy import CStrategy

from operators.c.analysis.rewriting import boolean, movable_branch


class DisjunctionBranchMerging(CStrategy):
    strategy_id = "CC14"
    node_types = {"if_statement"}

    def analyze_site(self, ctx, node):
        if not self.function_safe(ctx, node):
            return self.reject(ctx, node, "unsupported_function_control")
        inner = ctx.alternative(node)
        if inner is None or inner.type != "if_statement" or ctx.alternative(inner) is not None:
            return self.reject(ctx, node, "not_exact_disjunction_else_if")
        a, b = node.child_by_field_name("condition"), inner.child_by_field_name("condition")
        first, second = node.child_by_field_name("consequence"), inner.child_by_field_name("consequence")
        if not boolean(ctx, a) or not boolean(ctx, b) or not movable_branch(ctx, first) or ctx.text(first) != ctx.text(second):
            return self.reject(ctx, node, "conditions_unknown_or_bodies_differ")
        return [self.accept(ctx, node, f"if (({ctx.text(a)}) || ({ctx.text(b)})) {{ {ctx.text(first)} }}", "short_circuit_disjunction_merge")]
