"""C11 SD1: DeclarationExchange."""
from operators.c.tools.strategy import CStrategy
from operators.base.candidate import Candidate
from operators.tools.source import walk, unwrap


class DeclarationExchange(CStrategy):
    strategy_id = "SD1"
    node_types = {"compound_statement"}

    def analyze_site(self, ctx, node):
        out = []
        if not self.function_safe(ctx, node):
            return self.reject(ctx, node, "complex_scope_or_control")
        for a, b in self.adjacent(ctx, node):
            x, y = ctx.declaration(a), ctx.declaration(b)
            if (
                not x
                or not y
                or x.name == y.name
                or not x.initializer
                or not y.initializer
                or not ctx.total(x.initializer)
                or not ctx.total(y.initializer)
            ):
                continue
            if any(
                ctx.text(n) in {x.name, y.name}
                for init in (x.initializer, y.initializer)
                for n in walk(init)
                if n.type == "identifier"
            ):
                continue
            out.append(
                Candidate(
                    a,
                    [ctx.edit(a, ctx.text(b)), ctx.edit(b, ctx.text(a))],
                    "independent_declaration_exchange",
                )
            )
        return out
