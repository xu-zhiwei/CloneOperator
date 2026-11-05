"""C11 CL3: ForToWhile."""
from operators.c.tools.strategy import CStrategy
from operators.c.tools.control import for_parts, loop_body


class ForToWhile(CStrategy):
    strategy_id = "CL3"
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
                "{ " + init + " while (" + cond + ") { " + body + " " + update + " } }",
                "c_loop_conversion",
            )
        ]
