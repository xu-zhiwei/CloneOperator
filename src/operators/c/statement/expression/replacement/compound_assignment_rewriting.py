"""C11 SE6: CompoundAssignmentRewriting."""
from operators.c.tools.strategy import CStrategy


class CompoundAssignmentRewriting(CStrategy):
    strategy_id = "SE6"
    node_types = {"expression_statement"}

    def analyze_site(self, ctx, node):
        info = ctx.assignment(node)
        if not info or ctx.op(info[2]) not in {"+=", "-=", "*="}:
            return self.reject(ctx, node, "compound_assignment_not_pure_int")
        symbol, rhs, expr = info
        op = ctx.op(expr)[0]
        return [
            self.accept(
                ctx,
                node,
                f"{symbol.name} = {symbol.name} {op} ({ctx.text(rhs)});",
                "scalar_compound_expansion",
            )
        ]
