"""C11 CC9: ConditionalFlattening."""
from operators.c.tools.strategy import CStrategy
from operators.c.analysis.context import statements


class ConditionalFlattening(CStrategy):
    strategy_id = "CC9"
    node_types = {"if_statement"}

    def analyze_site(self, ctx, node):
        body = node.child_by_field_name("consequence")
        inner = (
            statements(body)[0]
            if body.type == "compound_statement" and len(statements(body)) == 1
            else body
        )
        if (
            not self.function_safe(ctx, node)
            or ctx.alternative(node)
            or inner.type != "if_statement"
            or ctx.alternative(inner)
        ):
            return self.reject(ctx, node, "not_exact_nested_if")
        a, b = (
            node.child_by_field_name("condition"),
            inner.child_by_field_name("condition"),
        )
        if not ctx.pure(a) or not ctx.pure(b):
            return self.reject(ctx, node, "unknown_condition_effects")
        return [
            self.accept(
                ctx,
                node,
                f'if ({ctx.text(a)} && {ctx.text(b)}) {{ {ctx.text(inner.child_by_field_name("consequence"))} }}',
                "short_circuit_conditional_flattening",
            )
        ]
