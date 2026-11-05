"""C11 CC1: IndependentCaseGroupPermutation."""
from operators.c.tools.strategy import CStrategy
from operators.c.tools.control import switch_safe


class IndependentCaseGroupPermutation(CStrategy):
    strategy_id = "CC1"
    node_types = {"switch_statement"}

    def analyze_site(self, ctx, node):
        checked = switch_safe(ctx, node)
        if not self.function_safe(ctx, node) or not checked:
            return self.reject(ctx, node, "case_fallthrough_or_complex_control")
        _, gs = checked
        if len(gs) < 2:
            return self.reject(ctx, node, "fewer_than_two_case_groups")
        a, b = gs[:2]

        def rendered(g):
            labels = " ".join(
                "default:" if v is None else f"case {v}:" for v in g.labels
            )
            return labels + " " + g.body(ctx)

        body = node.child_by_field_name("body")
        swapped = [b, a] + gs[2:]
        return [
            self.accept(
                ctx,
                body,
                "{ " + " ".join(rendered(g) for g in swapped) + " }",
                "complete_case_group_permutation",
            )
        ]
