"""C11 CL2: RedundantLoopRemoval."""
from operators.c.tools.strategy import CStrategy
from operators.tools.source import walk, unwrap
from operators.c.analysis.context import statements


class RedundantLoopRemoval(CStrategy):
    strategy_id = "CL2"
    node_types = {"for_statement", "while_statement"}

    def analyze_site(self, ctx, node):
        if not self.function_safe(ctx, node):
            return self.reject(ctx, node, "complex_scope_or_control")
        cond = node.child_by_field_name("condition")
        zero = ctx.constant(cond) == 0
        # Recognize only an immediately preceding, unused zero-valued scalar
        # controlling a while. Its declaration remains in the source.
        s = ctx.binding(unwrap(cond)) if cond else None
        if (
            not zero
            and s
            and s.initializer
            and ctx.constant(s.initializer) == 0
            and node.parent == s.declaration.parent
        ):
            items = statements(node.parent)
            idx = items.index(node)
            zero = (
                idx > 0
                and items[idx - 1] == s.declaration
                and all(
                    node.start_byte <= r.start_byte < node.end_byte
                    for r in ctx.references_of(s)
                )
            )
        init = node.child_by_field_name("initializer")
        if not zero or init is not None:
            return self.reject(ctx, node, "loop_not_provably_zero_or_has_initializer")
        return [self.accept(ctx, node, ";", "zero_iteration_loop_removal")]
