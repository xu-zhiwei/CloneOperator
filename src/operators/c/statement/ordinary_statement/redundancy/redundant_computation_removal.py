"""C11 SS3: RedundantComputationRemoval."""
from operators.c.tools.strategy import CStrategy
from operators.base.candidate import Candidate


class RedundantComputationRemoval(CStrategy):
    strategy_id = "SS3"
    node_types = {"compound_statement"}

    def analyze_site(self, ctx, node):
        if not self.function_safe(ctx, node):
            return self.reject(ctx, node, "complex_scope_or_control")
        out = []
        for a, b in self.adjacent(ctx, node):
            s, info = ctx.declaration(a), ctx.assignment(b)
            if (
                not s
                or not s.initializer
                or not ctx.total(s.initializer)
                or not info
                or info[0] is not s
                or ctx.op(info[2]) != "="
                or not ctx.total(info[1])
            ):
                continue
            if any(
                not (b.start_byte <= n.start_byte < b.end_byte)
                for n in ctx.references_of(s)
            ):
                continue
            out.append(
                Candidate(
                    a,
                    [ctx.edit(a, ""), ctx.edit(b, "")],
                    "dead_local_computation_removal",
                )
            )
        return out
