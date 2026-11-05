"""SE2: ExpressionRedundantWrapping."""
from operators.base.candidate import AnalyzedStrategy


class ExpressionRedundantWrapping(AnalyzedStrategy):
    strategy_id = "SE2"
    node_types = {"identifier", "binary_expression", "unary_expression"}

    def __init__(self, modes=("add_zero", "subtract_zero", "multiply_one"), **kwargs):
        super().__init__(**kwargs)
        self.modes = self.validate_modes(
            modes, {"add_zero", "subtract_zero", "multiply_one", "xor_zero"}
        )

    @staticmethod
    def read_position(node):
        outer = node
        while outer.parent and outer.parent.type == "parenthesized_expression":
            outer = outer.parent
        parent = outer.parent
        if parent is None:
            return False
        if parent.type in {
            "return_statement",
            "binary_expression",
            "argument_list",
            "unary_expression",
        }:
            return True
        return parent.type in {"variable_declarator", "assignment_expression"} and (
            parent.child_by_field_name("value") == outer
            or parent.child_by_field_name("right") == outer
        )

    def analyze_site(self, ctx, node):
        if not self.read_position(node) or ctx.integer(node) is not None:
            return []
        typ = ctx.expression_type(node)
        if typ not in {"int", "long"} or not ctx.pure(node):
            return self.reject(
                ctx,
                node,
                "unsafe_wrapping_type_or_effect",
                java_type=typ,
                effects=sorted(ctx.effects(node).reasons),
            )
        suffix = "L" if typ == "long" else ""
        operations = {
            "add_zero": ("+", 0),
            "subtract_zero": ("-", 0),
            "multiply_one": ("*", 1),
            "xor_zero": ("^", 0),
        }
        return [
            self.accept(
                ctx,
                node,
                f"(({ctx.text(node)}) {operations[m][0]} {operations[m][1]}{suffix})",
                m,
            )
            for m in self.modes
        ]
