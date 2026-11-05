"""C11 SE4: RelationalExpressionRewriting."""
from operators.c.tools.strategy import CStrategy
from operators.tools.source import walk, unwrap


class RelationalExpressionRewriting(CStrategy):
    strategy_id = "SE4"
    node_types = {"binary_expression"}

    def analyze_site(self, ctx, node):
        inverse = {"<": ">", "<=": ">=", ">": "<", ">=": "<="}
        op = ctx.op(node)
        l, r = node.child_by_field_name("left"), node.child_by_field_name("right")
        if (
            op not in inverse
            or not ctx.pure(node)
            or any(
                unwrap(x).type not in {"identifier", "number_literal"} for x in (l, r)
            )
        ):
            return self.reject(ctx, node, "relational_type_or_effect_unknown")
        return [
            self.accept(
                ctx,
                node,
                f"({ctx.text(r)} {inverse[op]} {ctx.text(l)})",
                "relational_operand_exchange",
            )
        ]
