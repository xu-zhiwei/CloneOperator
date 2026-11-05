"""CC3: RedundantBranchRemoval."""
from operators.base.candidate import AnalyzedStrategy
from operators.java.control.conditional.tools import checked_exception_risk, constant_boolean


class RedundantBranchRemoval(AnalyzedStrategy):
    strategy_id = "CC3"
    node_types = {"if_statement"}

    def analyze_site(self, ctx, node):
        condition = node.child_by_field_name("condition")
        value = constant_boolean(ctx, condition)
        if value is None:
            return self.reject(ctx, node, "branch_condition_not_proven_constant")
        body, other = (
            node.child_by_field_name("consequence"),
            node.child_by_field_name("alternative"),
        )
        live, dead = (body, other) if value else (other, body)
        if dead is not None and checked_exception_risk(dead):
            return self.reject(ctx, dead, "removal_may_invalidate_checked_catch")
        # Java gives if statements special reachability rules even when the
        # condition is a constant. Removing the if must not make a successor
        # unreachable. Keep an if(true) shell when the live arm is abrupt.
        if live is not None:
            from operators.java.analysis.completion import completion_outcomes
            if ("normal", None) not in completion_outcomes(ctx, live):
                if dead is not None and ("normal", None) not in completion_outcomes(ctx, dead):
                    # Both original arms may establish definite assignment or
                    # return. Preserve that fact by using the live arm twice.
                    replacement = "if (true) {\n" + ctx.text(live) + "\n} else {\n" + ctx.text(live) + "\n}"
                else:
                    replacement = "if (true) {\n" + ctx.text(live) + "\n}"
                if replacement == ctx.text(node):
                    return []
                return [self.accept(ctx, node, replacement, "remove_dead_arm_keep_reachability", constant=value)]
        replacement = "{ " + ctx.text(live) + " }" if live is not None else "{ }"
        return [
            self.accept(
                ctx, node, replacement, "remove_constant_branch", constant=value
            )
        ]
