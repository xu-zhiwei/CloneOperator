"""C11 SS1: IndependentComputationExchange."""
from operators.c.tools.strategy import CStrategy
from operators.base.candidate import Candidate


class IndependentComputationExchange(CStrategy):
    strategy_id = "SS1"
    node_types = {"compound_statement"}

    def analyze_site(self, ctx, node):
        if not self.function_safe(ctx, node):
            return self.reject(ctx, node, "complex_scope_or_control")
        out = []
        for a, b in self.adjacent(ctx, node):
            x, y = ctx.assignment_effects(a), ctx.assignment_effects(b)
            if x.independent(y) and x.writes and y.writes:
                out.append(
                    Candidate(
                        a,
                        [ctx.edit(a, ctx.text(b)), ctx.edit(b, ctx.text(a))],
                        "independent_scalar_assignments",
                    )
                )
        return out
