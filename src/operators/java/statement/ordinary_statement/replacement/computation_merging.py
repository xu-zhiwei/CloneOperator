"""SS5: ComputationMerging."""
from operators.base.candidate import Candidate
from operators.java.statement.declaration.tools import DeclarationStrategy
from operators.java.analysis.semantic import contains, statements
from operators.java.statement.ordinary_statement.tools import value_expression


class ComputationMerging(DeclarationStrategy):
    strategy_id = "SS5"

    def __init__(self, max_distance=4, **kwargs):
        super().__init__(**kwargs)
        if max_distance < 1:
            raise ValueError("max_distance must be positive")
        self.max_distance = max_distance

    def analyze_site(self, ctx, node):
        symbols = self.analyze_declaration(ctx, node, allow_multiple=False)
        if not symbols:
            return []
        symbol = symbols[0]
        if symbol.initializer is None or symbol.java_type not in {"int", "long"}:
            return []
        if ctx.expression_type(symbol.initializer) != symbol.java_type:
            return self.reject(ctx, node, "inlining_changes_numeric_promotion")
        references = ctx.references_of(symbol)
        if len(references) != 1 or ctx.captured_or_unresolved(symbol):
            return self.reject(ctx, node, "temporary_not_single_use")
        reference = references[0]
        sequence = statements(node.parent)
        index = sequence.index(node)
        for distance, target in enumerate(
            sequence[index + 1 : index + 1 + self.max_distance], 1
        ):
            expression = value_expression(target)
            if expression is None or not contains(expression, reference):
                continue
            if not ctx.pure(expression, {"int", "long", "boolean"}):
                return self.reject(
                    ctx, target, "inlining_target_has_effect_or_unknown_type"
                )
            initializer_effects = ctx.effects(symbol.initializer)
            for between in sequence[index + 1 : index + distance]:
                effects = ctx.effects(between)
                if effects.reasons or initializer_effects.reads & (
                    effects.writes | effects.declarations
                ):
                    return self.reject(
                        ctx, between, "initializer_inputs_change_before_use"
                    )
            return [
                Candidate(
                    node,
                    [
                        ctx.edit(node, ""),
                        ctx.edit(reference, f"({ctx.text(symbol.initializer)})"),
                    ],
                    "inline_single_use_temporary",
                    {"distance": distance, "name": symbol.name},
                )
            ]
        return self.reject(ctx, node, "temporary_use_outside_merge_window")
