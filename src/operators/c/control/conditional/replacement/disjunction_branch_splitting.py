"""c CC13: DisjunctionBranchSplitting. Checked directional transformation."""
from operators.c.tools.strategy import CStrategy
from operators.tools.source import unwrap
from operators.c.analysis.rewriting import boolean, movable_branch


class DisjunctionBranchSplitting(CStrategy):
    strategy_id = "CC13"
    node_types = {"if_statement"}

    def analyze_site(self, ctx, node):
        if not self.function_safe(ctx, node):
            return self.reject(ctx, node, "unsupported_function_control")
        cond = unwrap(node.child_by_field_name("condition"))
        body = node.child_by_field_name("consequence")
        if ctx.alternative(node) is not None or cond.type != "binary_expression" or ctx.op(cond) != "||" or not boolean(ctx, cond) or not movable_branch(ctx, body):
            return self.reject(ctx, node, "not_safe_disjunction_without_else")
        a, b = cond.child_by_field_name("left"), cond.child_by_field_name("right")
        return [self.accept(ctx, node, f"if ({ctx.text(a)}) {{ {ctx.text(body)} }} else if ({ctx.text(b)}) {{ {ctx.text(body)} }}", "short_circuit_disjunction_split")]
