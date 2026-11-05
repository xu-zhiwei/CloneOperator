"""C11 SD3: RedundantDeclarationRemoval."""
from operators.c.tools.strategy import CStrategy


class RedundantDeclarationRemoval(CStrategy):
    strategy_id = "SD3"
    node_types = {"declaration"}

    def analyze_site(self, ctx, node):
        s = ctx.declaration(node)
        if (
            not self.function_safe(ctx, node)
            or not s
            or ctx.references_of(s)
            or s.initializer is not None
            and not ctx.total(s.initializer)
        ):
            return self.reject(ctx, node, "declaration_used_or_initializer_unsafe")
        return [self.accept(ctx, node, "", "unused_int_declaration_removal")]
