"""java CC14: DisjunctionBranchMerging. Checked directional transformation."""
from operators.base.candidate import AnalyzedStrategy

from operators.java.analysis.rewriting import boolean, movable_branch


class DisjunctionBranchMerging(AnalyzedStrategy):
    strategy_id = "CC14"
    node_types = {"if_statement"}

    def analyze_site(self, ctx, node):
        inner = node.child_by_field_name("alternative")
        if inner is None or inner.type != "if_statement" or inner.child_by_field_name("alternative") is not None:
            return self.reject(ctx, node, "not_exact_disjunction_else_if")
        a, b = node.child_by_field_name("condition"), inner.child_by_field_name("condition")
        first, second = node.child_by_field_name("consequence"), inner.child_by_field_name("consequence")
        if not boolean(ctx, a) or not boolean(ctx, b) or not movable_branch(ctx, first) or ctx.text(first) != ctx.text(second):
            return self.reject(ctx, node, "conditions_unknown_or_bodies_differ")
        return [self.accept(ctx, node, f"if (({ctx.text(a)}) || ({ctx.text(b)})) {{ {ctx.text(first)} }}", "short_circuit_disjunction_merge")]
