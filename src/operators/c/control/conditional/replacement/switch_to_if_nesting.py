"""C11 CC6: SwitchToIfNesting."""
from operators.c.tools.strategy import CStrategy
from operators.c.tools.control import switch_safe


class SwitchToIfNesting(CStrategy):
    strategy_id = "CC6"
    node_types = {"switch_statement"}

    def analyze_site(self, ctx, node):
        checked = switch_safe(ctx, node, allow_fallthrough=True)
        if not self.function_safe(ctx, node) or not checked:
            return self.reject(ctx, node, "switch_control_or_binding_unknown")
        selector, gs = checked
        name = ctx.fresh(node, "sctSelector")
        all_values = [v for g in gs for v in g.labels if v is not None]

        def condition(g):
            terms = [f"{name} == {v}" for v in g.labels if v is not None]
            if None in g.labels:
                terms.append(
                    "(" + " && ".join((f"{name} != {v}" for v in all_values)) + ")"
                    if all_values
                    else "1"
                )
            return " || ".join(terms)

        parts = []
        active = ctx.fresh(node, "sctActive")
        parts.append(f"int {active} = 0;")
        for g in gs:
            parts.append(f"if ({condition(g)}) {active} = 1;")
            ending = (
                f"{active} = 0;"
                if g.nodes and g.nodes[-1].type == "break_statement"
                else ""
            )
            parts.append(
                f"if ({active}) {{ "
                + g.body(ctx, strip_break=True)
                + " "
                + ending
                + " }"
            )
        return [
            self.accept(
                ctx,
                node,
                f"{{ int {name} = {ctx.text(selector)}; " + " ".join(parts) + " }",
                "switch_if_nesting",
            )
        ]
