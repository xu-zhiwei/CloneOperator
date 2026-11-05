"""C11 SS2: RedundantComputationInsertion."""
from operators.c.tools.strategy import CStrategy
from operators.base.candidate import Candidate
from operators.base.results import Edit


class RedundantComputationInsertion(CStrategy):
    strategy_id = "SS2"
    node_types = {"compound_statement"}

    def analyze_site(self, ctx, node):
        if node.parent.type != "function_definition" or not self.function_safe(
            ctx, node
        ):
            return self.reject(ctx, node, "not_safe_function_entry")
        name = ctx.fresh(node)
        return [
            Candidate(
                node,
                [
                    Edit(
                        node.start_byte + 1,
                        node.start_byte + 1,
                        f" {{ int {name} = 0; {name} = 1 + 2; }} ",
                    )
                ],
                "isolated_redundant_computation",
            )
        ]
