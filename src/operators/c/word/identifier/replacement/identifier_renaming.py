"""C11 WI1: IdentifierRenaming."""
from operators.c.tools.strategy import CStrategy
from operators.base.candidate import Candidate
from operators.tools.source import walk, unwrap
from operators.c.tools.names import C_KEYWORDS


class IdentifierRenaming(CStrategy):
    strategy_id = "WI1"
    node_types = {"parameter_declaration", "declaration"}

    def __init__(self, name_provider=None, **kwargs):
        super().__init__(**kwargs)
        self.name_provider = name_provider

    def analyze_site(self, ctx, node):
        symbols = [
            s
            for s in ctx.symbols
            if s.declaration == node and s.supported and not s.escaped
        ]
        out = []
        for s in symbols:
            if s.initializer and any(
                ctx.resolve(n) is s
                for n in walk(s.initializer)
                if n.type == "identifier"
            ):
                continue
            name = ctx.fresh(node, "sctName")
            if self.name_provider:
                name = self.name_provider(s.name)
                if (
                    not isinstance(name, str)
                    or not name.isascii()
                    or not name.isidentifier()
                    or name.startswith("_")
                    or name in C_KEYWORDS
                    or any(
                        ctx.text(n) == name
                        for n in ctx.nodes
                        if n.type
                        in {"identifier", "type_identifier", "field_identifier"}
                    )
                ):
                    ctx.reject(node, "unsafe_name_candidate")
                    continue
            edits = [ctx.edit(n, name) for n in [s.node] + ctx.references_of(s)]
            out.append(
                Candidate(
                    node,
                    edits,
                    "bound_identifier_renaming",
                    {"before": s.name, "after": name},
                )
            )
        return out
