"""SE3: ExpressionRedundantUnwrapping."""
from operators.java.statement.expression.tools import BinaryExpressionStrategy


class ExpressionRedundantUnwrapping(BinaryExpressionStrategy):
    strategy_id = "SE3"

    def analyze_site(self, ctx, node):
        op = ctx.op(node)
        if op not in {"+", "-", "*", "^"}:
            return []
        a, b = self.operands(ctx, node)
        choices = [(a, b)] + ([(b, a)] if op in {"+", "*", "^"} else [])
        for expression, identity in choices:
            literal = ctx.integer(identity)
            if (
                literal is None
                or literal[0] != (1 if op == "*" else 0)
                or ctx.integer(expression) is not None
            ):
                continue
            if ctx.pure(expression) and ctx.expression_type(
                expression
            ) == ctx.expression_type(node):
                return [
                    self.accept(
                        ctx, node, ctx.text(expression), "remove_expression_identity"
                    )
                ]
            return self.reject(ctx, node, "identity_removal_changes_type_or_effect")
        return []
