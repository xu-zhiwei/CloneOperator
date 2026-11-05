"""C11 SD4: DeclarationSplitting."""
from operators.c.tools.strategy import CStrategy


class DeclarationSplitting(CStrategy):
    strategy_id = "SD4"
    node_types = {"declaration"}

    def analyze_site(self, ctx, node):
        s = ctx.declaration(node)
        if (
            not self.function_safe(ctx, node)
            or not s
            or s.initializer is None
            or not ctx.pure(s.initializer)
        ):
            return self.reject(ctx, node, "not_splittable_int_declaration")
        return [
            self.accept(
                ctx,
                node,
                f"int {s.name}; {s.name} = {ctx.text(s.initializer)};",
                "int_declaration_splitting",
            )
        ]
