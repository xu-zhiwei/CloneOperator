"""SS3: RedundantComputationRemoval."""
from operators.base.candidate import Candidate
from operators.java.statement.declaration.tools import DeclarationStrategy
from operators.tools.source import ancestor
from operators.java.statement.ordinary_statement.tools import computational


class RedundantComputationRemoval(DeclarationStrategy):
    strategy_id = "SS3"

    def analyze_site(self, ctx, node):
        symbols = self.analyze_declaration(ctx, node, allow_multiple=False)
        if not symbols:
            return []
        symbol = symbols[0]
        if symbol.java_type not in {"int", "long"} or symbol.initializer is None:
            return []
        if ctx.captured_or_unresolved(symbol):
            return self.reject(ctx, node, "dead_computation_binding_escapes")
        references = ctx.references_of(symbol)
        if not references:
            return []
        dead = []
        for reference in references:
            statement = ancestor(reference, "expression_statement")
            if (
                statement is None
                or statement.parent != node.parent
                or not computational(ctx, statement)
            ):
                return self.reject(ctx, reference, "dead_value_has_observed_use")
            effects = ctx.effects(statement)
            if effects.writes != {symbol.key}:
                return self.reject(
                    ctx, reference, "dead_computation_writes_other_binding"
                )
            if statement not in dead:
                dead.append(statement)
        return [
            Candidate(
                node,
                [
                    ctx.edit(n, "")
                    for n in sorted([node] + dead, key=lambda n: n.start_byte)
                ],
                "remove_dead_computation_slice",
                {"name": symbol.name, "statements": len(dead) + 1},
            )
        ]
