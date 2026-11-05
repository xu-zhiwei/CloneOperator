"""C11 CL6: DoWhileToFor."""
from operators.c.tools.strategy import CStrategy


class DoWhileToFor(CStrategy):
    strategy_id = "CL6"
    node_types = {"do_statement"}

    def analyze_site(self, ctx, node):
        if not self.function_safe(ctx, node):
            return self.reject(ctx, node, "complex_loop_control_or_scope")
        body = ctx.text(node.child_by_field_name("body"))
        cond = ctx.text(node.child_by_field_name("condition")) or "1"
        # Keep a constant loop header: C11 permits termination assumptions for
        # some nonconstant loops (6.8.5p6). Do not weaken an original constant
        # controlling expression by OR-ing it with a mutable flag.
        flag = ctx.fresh(node, "sctFirst")
        return [
            self.accept(
                ctx,
                node,
                f"{{ int {flag} = 1; for (; 1; {flag} = 0) {{ if (!{flag} && !({cond})) break; {body} }} }}",
                "c_loop_conversion",
            )
        ]
