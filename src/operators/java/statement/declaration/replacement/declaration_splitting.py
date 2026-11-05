"""SD4: DeclarationSplitting."""
from operators.java.statement.declaration.tools import DeclarationStrategy


class DeclarationSplitting(DeclarationStrategy):
    strategy_id = "SD4"

    def __init__(self, allow_multiple=True, **kwargs):
        super().__init__(**kwargs)
        self.allow_multiple = allow_multiple

    def analyze_site(self, ctx, node):
        symbols = self.analyze_declaration(
            ctx, node, allow_multiple=self.allow_multiple, require_pure=False
        )
        if symbols is None or not any(s.initializer is not None for s in symbols):
            return []
        # For multi-declarators, do not move all declarations ahead of all
        # initializations; a later initializer can depend on an earlier one.
        parts = []
        for s in symbols:
            if s.java_type == "var":
                return self.reject(
                    ctx, node, "inferred_declaration_requires_initializer"
                )
            parts.append(f"{s.java_type} {s.name};")
            if s.initializer is not None:
                value = ctx.text(s.initializer)
                if s.initializer.type == "array_initializer":
                    value = f"new {s.java_type} {value}"
                parts.append(f"{s.name} = {value};")
        return [
            self.accept(
                ctx,
                node,
                "\n".join(parts),
                "split_initialization",
                names=[s.name for s in symbols],
            )
        ]
