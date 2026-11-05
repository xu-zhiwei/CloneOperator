"""C11 CC3: RedundantBranchRemoval."""
from operators.c.tools.strategy import CStrategy


class RedundantBranchRemoval(CStrategy):
    strategy_id = "CC3"
    node_types = {"if_statement"}

    def analyze_site(self, ctx, node):
        cond = node.child_by_field_name("condition")
        if not self.function_safe(ctx, node) or ctx.constant(cond) != 0:
            return self.reject(ctx, node, "condition_not_provably_false")
        alt = ctx.alternative(node)
        return [
            self.accept(
                ctx,
                node,
                "{ " + ctx.text(alt) + " }" if alt else ";",
                "false_branch_removal",
            )
        ]
