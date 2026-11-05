"""CC8: ConditionalNesting."""
from operators.java.control.conditional.tools import ConditionalStrategy


class ConditionalNesting(ConditionalStrategy):
    strategy_id = "CC8"

    def analyze_site(self, ctx, node):
        condition = self.ordinary_condition(ctx, node)
        if condition is None:
            return []
        if node.child_by_field_name("alternative") is not None:
            return self.reject(ctx, node, "nesting_would_duplicate_else")
        if condition.type != "binary_expression" or ctx.op(condition) != "&&":
            return []
        a, b = (
            condition.child_by_field_name("left"),
            condition.child_by_field_name("right"),
        )
        body = node.child_by_field_name("consequence")
        return [
            self.accept(
                ctx,
                node,
                f"if ({ctx.text(a)}) {{ if ({ctx.text(b)}) {{ {ctx.text(body)} }} }}",
                "short_circuit_nesting",
            )
        ]
