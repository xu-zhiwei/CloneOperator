"""C11 CL4: WhileToFor."""
from operators.c.tools.strategy import CStrategy


class WhileToFor(CStrategy):
    strategy_id = "CL4"
    node_types = {"while_statement"}

    def analyze_site(self, ctx, node):
        if not self.function_safe(ctx, node):
            return self.reject(ctx, node, "complex_loop_control_or_scope")
        body = ctx.text(node.child_by_field_name("body"))
        cond = ctx.text(node.child_by_field_name("condition")) or "1"
        return [
            self.accept(
                ctx, node, "for (; " + cond + "; ) " + body, "c_loop_conversion"
            )
        ]
