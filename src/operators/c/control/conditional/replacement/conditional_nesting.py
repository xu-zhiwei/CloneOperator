"""C11 CC8: ConditionalNesting."""
from operators.c.tools.strategy import CStrategy
from operators.tools.source import walk, unwrap


class ConditionalNesting(CStrategy):
    strategy_id = "CC8"
    node_types = {"if_statement"}

    def analyze_site(self, ctx, node):
        cond = unwrap(node.child_by_field_name("condition"))
        if (
            not self.function_safe(ctx, node)
            or ctx.alternative(node)
            or cond.type != "binary_expression"
            or ctx.op(cond) != "&&"
            or not ctx.pure(cond)
        ):
            return self.reject(ctx, node, "not_safe_conjunction_without_else")
        l, r = cond.child_by_field_name("left"), cond.child_by_field_name("right")
        body = node.child_by_field_name("consequence")
        return [
            self.accept(
                ctx,
                node,
                f"if ({ctx.text(l)}) {{ if ({ctx.text(r)}) {{ {ctx.text(body)} }} }}",
                "short_circuit_conditional_nesting",
            )
        ]
