"""C11 CC4: IfToSwitchNesting."""
from operators.c.tools.strategy import CStrategy
from operators.c.tools.control import if_chain


class IfToSwitchNesting(CStrategy):
    strategy_id = "CC4"
    node_types = {"if_statement"}

    def analyze_site(self, ctx, node):
        checked = if_chain(ctx, node)
        if not self.function_safe(ctx, node) or not checked:
            return self.reject(ctx, node, "not_stable_integer_equality_chain")
        selector, branches, default = checked
        parts = []
        for values, body in branches:
            parts.append(
                " ".join((f"case {v}:" for v in values)) + " " + body + " break;"
            )
        if default is not None:
            parts.append("default: " + default)
        return [
            self.accept(
                ctx,
                node,
                "switch (" + selector.name + ") { " + " ".join(parts) + " }",
                "if_switch_nesting",
            )
        ]
