"""CC10: ConditionInversionAndBranchExchange."""
from operators.java.control.conditional.tools import ConditionalStrategy

from operators.tools.source import unwrap


class ConditionInversionAndBranchExchange(ConditionalStrategy):
    strategy_id = "CC10"

    def analyze_site(self, ctx, node):
        condition = self.ordinary_condition(ctx, node)
        other = node.child_by_field_name("alternative")
        if condition is None:
            return []
        if other is None:
            return self.reject(ctx, node, "inversion_requires_else")
        body = node.child_by_field_name("consequence")
        original = unwrap(condition)
        inverted = (ctx.text(original.named_children[-1]) if original.type == "unary_expression" and ctx.op(original) == "!" else f"!({ctx.text(condition)})")
        return [
            self.accept(
                ctx,
                node,
                f"if ({inverted}) {{ {ctx.text(other)} }} else {{ {ctx.text(body)} }}",
                "invert_and_exchange",
            )
        ]
