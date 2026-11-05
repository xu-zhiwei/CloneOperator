"""C11 SD5: DeclarationMerging."""
from operators.c.tools.strategy import CStrategy
from operators.base.candidate import Candidate


class DeclarationMerging(CStrategy):
    strategy_id = "SD5"
    node_types = {"compound_statement"}

    def analyze_site(self, ctx, node):
        if not self.function_safe(ctx, node):
            return self.reject(ctx, node, "complex_scope_or_control")
        out = []
        for a, b in self.adjacent(ctx, node):
            s, info = ctx.declaration(a), ctx.assignment(b)
            if (
                not s
                or s.initializer is not None
                or not info
                or info[0] is not s
                or ctx.op(info[2]) != "="
                or s.key in ctx.effects(info[1]).reads
            ):
                continue
            out.append(
                Candidate(
                    a,
                    [
                        ctx.edit(a, f"int {s.name} = {ctx.text(info[1])};"),
                        ctx.edit(b, ""),
                    ],
                    "int_declaration_merging",
                )
            )
        return out
