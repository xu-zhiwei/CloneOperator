"""C11 SE5: IncrementDecrementRewriting."""
from operators.c.tools.strategy import CStrategy


class IncrementDecrementRewriting(CStrategy):
    strategy_id = "SE5"
    node_types = {"expression_statement"}

    def analyze_site(self, ctx, node):
        if (
            len(node.named_children) != 1
            or node.named_children[0].type != "update_expression"
        ):
            return self.reject(ctx, node, "not_standalone_update")
        expr = node.named_children[0]
        argument = expr.child_by_field_name("argument")
        symbol = ctx.binding(argument)
        if not symbol or not ctx.initialized(symbol, argument):
            return self.reject(ctx, node, "update_binding_unknown")
        op = "+=" if ctx.op(expr) == "++" else "-="
        return [
            self.accept(
                ctx, node, f"{symbol.name} {op} 1;", "standalone_update_assignment"
            )
        ]
