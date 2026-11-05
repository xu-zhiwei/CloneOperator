"""C11 CC7: SwitchToIfCloning."""
from operators.c.tools.strategy import CStrategy
from operators.c.tools.control import switch_safe


class SwitchToIfCloning(CStrategy):
    strategy_id = "CC7"
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
        for i, g in enumerate(gs):
            tail = []
            for target in gs[i:]:
                tail.append(target.body(ctx, strip_break=True))
                if target.terminal:
                    break
            parts.append(
                ("if" if i == 0 else "else if")
                + " ("
                + condition(g)
                + ") { "
                + " ".join(tail)
                + " }"
            )
        return [
            self.accept(
                ctx,
                node,
                f"{{ int {name} = {ctx.text(selector)}; " + " ".join(parts) + " }",
                "switch_if_cloning",
            )
        ]
