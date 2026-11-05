"""c SE8: CompoundAssignmentContraction. Checked directional transformation."""
from operators.c.tools.strategy import CStrategy
from operators.tools.source import unwrap
from operators.c.analysis.rewriting import writable


class CompoundAssignmentContraction(CStrategy):
    strategy_id = "SE8"
    node_types = {"expression_statement"}

    def analyze_site(self, ctx, node):
        if len(node.named_children) != 1:
            return []
        expr = node.named_children[0]
        if expr.type != "assignment_expression":
            return []
        s = writable(ctx, expr.child_by_field_name("left"))
        if not s:
            return self.reject(ctx, node, "unsupported_assignment_binding")
        rhs = unwrap(expr.child_by_field_name("right"))

        if ctx.op(expr) == "=" and rhs.type == "binary_expression":
            old = unwrap(rhs.child_by_field_name("left"))
            if writable(ctx, old) is not s:
                return self.reject(ctx, node, "rhs_does_not_read_same_target_first")
            op, operand = ctx.op(rhs), rhs.child_by_field_name("right")
        elif self.strategy_id == "SE7" and ctx.op(expr) in {"+=", "-="}:
            op, operand = ctx.op(expr)[0], rhs
        else:
            return []
        if not ctx.initialized(s, node) or not ctx.pure(rhs):
            return self.reject(ctx, node, "rhs_not_initialized_pure_int")
        allowed = {"+", "-", "*", "&", "|", "^"} if self.language == "java" else {"+", "-", "*"}
        if op not in allowed:
            return self.reject(ctx, node, "unsupported_compound_operator")
        replacement = f"{s.name} {op}= ({ctx.text(operand)});"
        return [self.accept(ctx, node, replacement, "local_assignment_contraction")]
