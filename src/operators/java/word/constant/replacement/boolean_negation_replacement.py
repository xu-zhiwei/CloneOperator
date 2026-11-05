"""WC4: BooleanNegationReplacement."""
from operators.base.candidate import AnalyzedStrategy


class BooleanNegationReplacement(AnalyzedStrategy):
    strategy_id = "WC4"
    node_types = {"true", "false"}

    def analyze_site(self, ctx, node):
        return [
            self.accept(
                ctx,
                node,
                "(!false)" if node.type == "true" else "(!true)",
                "boolean_negation",
            )
        ]
