"""C11 CL7: DoWhileToWhile."""
from operators.c.tools.strategy import CStrategy


class DoWhileToWhile(CStrategy):
    strategy_id = "CL7"
    node_types = {"do_statement"}

    def analyze_site(self, ctx, node):
        if not self.function_safe(ctx, node):
            return self.reject(ctx, node, "complex_loop_control_or_scope")
        body = ctx.text(node.child_by_field_name("body"))
        cond = ctx.text(node.child_by_field_name("condition")) or "1"
        # The constant header avoids introducing C11's nonconstant-loop
        # termination assumption. The flag guards the original test instead.
        flag = ctx.fresh(node, "sctFirst")
        return [
            self.accept(
                ctx,
                node,
                f"{{ int {flag} = 1; while (1) {{ if (!{flag} && !({cond})) break; {flag} = 0; {body} }} }}",
                "c_loop_conversion",
            )
        ]
