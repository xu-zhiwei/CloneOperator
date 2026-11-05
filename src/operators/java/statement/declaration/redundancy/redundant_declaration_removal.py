"""SD3: RedundantDeclarationRemoval."""
from operators.java.statement.declaration.tools import DeclarationStrategy


class RedundantDeclarationRemoval(DeclarationStrategy):
    strategy_id = "SD3"

    def analyze_site(self, ctx, node):
        symbols = self.analyze_declaration(ctx, node)
        if symbols is None:
            return []
        unused = [
            s
            for s in symbols
            if not ctx.references_of(s) and not ctx.captured_or_unresolved(s)
        ]
        if not unused:
            return self.reject(ctx, node, "declaration_is_live_or_captured")
        if len(unused) == len(symbols):
            return [
                self.accept(
                    ctx,
                    node,
                    "",
                    "remove_unused_declaration",
                    names=[s.name for s in unused],
                )
            ]
        # Preserve remaining declarators verbatim, including their original order.
        live = [ctx.text(s.declaration) for s in symbols if s not in unused]
        typ = ctx.text(node.child_by_field_name("type"))
        return [
            self.accept(
                ctx,
                node,
                typ + " " + ", ".join(live) + ";",
                "remove_unused_declarators",
                names=[s.name for s in unused],
            )
        ]
