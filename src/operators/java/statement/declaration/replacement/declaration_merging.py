"""SD5: DeclarationMerging."""
from operators.base.candidate import Candidate
from operators.java.statement.declaration.tools import DeclarationStrategy
from operators.java.analysis.semantic import PRIMITIVES, contains, statements
from operators.tools.source import walk


class DeclarationMerging(DeclarationStrategy):
    strategy_id = "SD5"

    def __init__(self, max_distance=1, **kwargs):
        super().__init__(**kwargs)
        if max_distance < 1:
            raise ValueError("max_distance must be positive")
        self.max_distance = max_distance

    def analyze_site(self, ctx, node):
        symbols = self.analyze_declaration(ctx, node, allow_multiple=False)
        if not symbols:
            return []
        symbol = symbols[0]
        if symbol.initializer is not None:
            return []
        sequence = statements(node.parent)
        index = sequence.index(node)
        for distance, target in enumerate(
            sequence[index + 1 : index + 1 + self.max_distance], 1
        ):
            if target.type != "expression_statement" or not target.named_children:
                continue
            expression = target.named_children[0]
            if expression.type != "assignment_expression" or ctx.op(expression) != "=":
                continue
            if ctx.resolve(expression.child_by_field_name("left")) is not symbol:
                continue
            rhs = expression.child_by_field_name("right")
            effects = ctx.effects(target)
            if any(
                n.type == "identifier" and ctx.resolve(n) is symbol for n in walk(rhs)
            ):
                return self.reject(ctx, target, "unsafe_initial_assignment")
            intervening = sequence[index + 1 : index + distance]
            if intervening and not ctx.pure(rhs, PRIMITIVES):
                return self.reject(
                    ctx, target, "effectful_initializer_cannot_move_across_statements"
                )
            if any(not effects.independent(ctx.effects(s)) for s in intervening):
                return self.reject(ctx, target, "merge_crosses_dependency_or_effect")
            if any(
                contains(s, r) for s in intervening for r in ctx.references_of(symbol)
            ):
                return self.reject(ctx, target, "variable_used_before_merge_assignment")
            return [
                Candidate(
                    node,
                    [
                        ctx.edit(
                            node, f"{symbol.java_type} {symbol.name} = {ctx.text(rhs)};"
                        ),
                        ctx.edit(target, ""),
                    ],
                    "merge_initialization",
                    {"distance": distance},
                )
            ]
        return self.reject(ctx, node, "no_matching_initial_assignment")
