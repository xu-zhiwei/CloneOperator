"""C11 CL5: ForToDoWhile."""
from operators.c.tools.strategy import CStrategy
from operators.c.tools.control import for_parts, loop_body


class ForToDoWhile(CStrategy):
    strategy_id = "CL5"
    node_types = {"for_statement"}

    def analyze_site(self, ctx, node):
        if not self.function_safe(ctx, node):
            return self.reject(ctx, node, "complex_loop_control_or_scope")
        body = ctx.text(node.child_by_field_name("body"))
        cond = ctx.text(node.child_by_field_name("condition")) or "1"

        init, cond, update = for_parts(ctx, node)
        body = loop_body(ctx, node, update)
        if body is None:
            return self.reject(ctx, node, "for_update_name_capture")
        update = update + ";" if update else ""
        return [
            self.accept(
                ctx,
                node,
                "{ "
                + init
                + " if ("
                + cond
                + ") { do { "
                + body
                + " "
                + update
                + " } while ("
                + cond
                + "); } }",
                "c_loop_conversion",
            )
        ]
