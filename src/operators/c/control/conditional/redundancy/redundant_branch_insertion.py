"""C11 CC2: RedundantBranchInsertion."""
from operators.c.tools.strategy import CStrategy
from operators.base.candidate import Candidate
from operators.base.results import Edit


class RedundantBranchInsertion(CStrategy):
    strategy_id = "CC2"
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
                        f" if (0) {{ int {name} = 0; }} ",
                    )
                ],
                "zero_branch_insertion",
            )
        ]
