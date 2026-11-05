"""C11 SS4: ComputationSplitting."""
from operators.c.tools.strategy import CStrategy
from operators.tools.source import walk, unwrap


class ComputationSplitting(CStrategy):
    strategy_id = "SS4"
    node_types = {"expression_statement"}

    def analyze_site(self, ctx, node):
        if node.parent.type != "compound_statement" or not self.function_safe(
            ctx, node
        ):
            return self.reject(ctx, node, "not_direct_computation")
        info = ctx.assignment(node)
        if not info or ctx.op(info[2]) != "=":
            return self.reject(ctx, node, "not_pure_assignment")
        rhs = unwrap(info[1])
        if rhs.type != "binary_expression" or ctx.op(rhs) in {"&&", "||"}:
            return self.reject(ctx, node, "no_unconditionally_evaluated_subexpression")
        child = rhs.child_by_field_name("left")
        if unwrap(child).type != "binary_expression" or not ctx.pure(child):
            return self.reject(ctx, node, "no_pure_subexpression")
        name = ctx.fresh(node)
        expr = ctx.source[info[1].start_byte : info[1].end_byte]
        start, end = (
            child.start_byte - info[1].start_byte,
            child.end_byte - info[1].start_byte,
        )
        replacement = (expr[:start] + name.encode() + expr[end:]).decode()
        return [
            self.accept(
                ctx,
                node,
                f"int {name} = {ctx.text(child)}; {info[0].name} = {replacement};",
                "preserved_tree_computation_splitting",
            )
        ]
