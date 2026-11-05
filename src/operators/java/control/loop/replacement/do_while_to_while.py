"""CL7: DoWhileToWhile."""
from operators.java.control.loop.tools import LoopStrategy, continue_target
from operators.java.analysis.completion import completion_outcomes
from operators.tools.source import walk


class DoWhileToWhile(LoopStrategy):
    strategy_id = "CL7"
    node_types = {"do_statement"}
    post_test_header = "while (true)"

    def __init__(self, mode="condition_at_end", **kwargs):
        super().__init__(**kwargs)
        if mode not in {"condition_at_end", "first_flag"}:
            raise ValueError("mode must be condition_at_end or first_flag")
        self.mode = mode

    def analyze_site(self, ctx, node):
        structure = self.analyze_structure(ctx, node)
        if structure is None:
            return []
        body, condition, labels, outer = structure
        label_prefix = "".join(label + ": " for label in labels)
        if self.mode == "first_flag":
            if labels or not self.first_flag_safe(ctx, node):
                return self.reject(
                    ctx, node, "first_flag_definite_assignment_or_label_risk"
                )
            flag = ctx.fresh(node, "first")
            replacement = f"{{ boolean {flag}=true; while ({flag} || {ctx.text(condition)}) {{ {flag}=false; {ctx.text(body)} }} }}"
            return [
                self.accept(ctx, outer, replacement, "first_iteration_flag", flag=flag)
            ]
        # A literal true while gives javac the same guaranteed first iteration
        # as do. A labeled body exit redirects only continues targeting this
        # exact loop to its trailing condition; nested loops are untouched.
        exit_label = ctx.fresh(node, "loopBody")
        continues = [
            n
            for n in walk(body)
            if n.type == "continue_statement" and continue_target(ctx, n) == node
        ]
        rewritten = ctx.source[body.start_byte : body.end_byte]
        for cont in sorted(continues, key=lambda n: n.start_byte, reverse=True):
            a, b = cont.start_byte - body.start_byte, cont.end_byte - body.start_byte
            rewritten = rewritten[:a] + f"break {exit_label};".encode() + rewritten[b:]
        body_text = rewritten.decode("utf-8")
        outcomes = completion_outcomes(
            ctx, body, {cont.id: exit_label for cont in continues}
        )
        reaches_condition = ("normal", None) in outcomes or (
            "break_statement",
            exit_label,
        ) in outcomes
        condition_value = ctx.constant_value(condition)
        if (
            reaches_condition
            and condition_value is None
            and self.unknown_constant_return_risk(ctx, node, condition)
        ):
            return self.reject(
                ctx, node, "external_constant_return_reachability_unknown"
            )
        if not reaches_condition:
            from operators.java.control.conditional.tools import checked_exception_risk
            if checked_exception_risk(condition):
                return self.reject(ctx, condition, "condition_removal_may_invalidate_checked_catch")
        if not reaches_condition or condition_value is True:
            trailing = ""
        elif condition_value is False:
            trailing = "break;"
        else:
            trailing = f"if (!{ctx.text(condition)}) break;"
        replacement = f"{label_prefix}{self.post_test_header} {{ {exit_label}: {{ {body_text} }} {trailing} }}"
        return [
            self.accept(
                ctx,
                outer,
                replacement,
                "condition_at_end",
                redirected_continues=len(continues),
                labels=labels,
            )
        ]
