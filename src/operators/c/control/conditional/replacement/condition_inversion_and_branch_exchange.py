"""C11 CC10: ConditionInversionAndBranchExchange."""
from operators.c.tools.strategy import CStrategy

from operators.tools.source import unwrap


class ConditionInversionAndBranchExchange(CStrategy):
    strategy_id = "CC10"
    node_types = {"if_statement"}

    def analyze_site(self, ctx, node):
        a, b = node.child_by_field_name("consequence"), ctx.alternative(node)
        cond = node.child_by_field_name("condition")
        if not self.function_safe(ctx, node) or not b or not ctx.pure(cond):
            return self.reject(ctx, node, "missing_else_or_unknown_condition")
        original = unwrap(cond)
        inverted = (ctx.text(original.named_children[-1]) if original.type == "unary_expression" and ctx.op(original) == "!" else f"!({ctx.text(cond)})")
        return [
            self.accept(
                ctx,
                node,
                f"if ({inverted}) {{ {ctx.text(b)} }} else {{ {ctx.text(a)} }}",
                "condition_inversion_branch_exchange",
            )
        ]
