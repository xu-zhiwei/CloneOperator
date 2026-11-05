"""SE6: CompoundAssignmentRewriting."""
from operators.base.candidate import AnalyzedStrategy
from operators.tools.source import unwrap


class CompoundAssignmentRewriting(AnalyzedStrategy):
    strategy_id = "SE6"
    node_types = {"assignment_expression"}

    def __init__(self, operators=("+=", "-=", "*=", "&=", "|=", "^="), **kwargs):
        super().__init__(**kwargs)
        self.operators = self.validate_modes(
            operators, {"+=", "-=", "*=", "&=", "|=", "^="}
        )

    def analyze_site(self, ctx, node):
        if ctx.op(node) not in self.operators:
            return []
        if node.parent.type != "expression_statement":
            return self.reject(ctx, node, "assignment_value_is_observed")
        left, right = (
            node.child_by_field_name("left"),
            node.child_by_field_name("right"),
        )
        symbol = ctx.resolve(unwrap(left))
        promoted = ctx.expression_type(right)
        if (
            symbol is None
            or symbol.final
            or symbol.java_type not in {"int", "long"}
            or not ctx.pure(right)
            or symbol.java_type == "int"
            and promoted == "long"
        ):
            return self.reject(
                ctx, node, "compound_assignment_requires_conversion_or_has_effects"
            )
        op = ctx.op(node)[:-1]
        return [
            self.accept(
                ctx,
                node,
                f"{ctx.text(left)} = {ctx.text(left)} {op} ({ctx.text(right)})",
                "expanded_compound_assignment",
                java_type=symbol.java_type,
            )
        ]
