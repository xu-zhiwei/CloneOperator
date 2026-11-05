"""SS1: IndependentComputationExchange."""
from operators.base.candidate import AnalyzedStrategy, Candidate
from operators.java.statement.ordinary_statement.tools import computational
from operators.java.analysis.semantic import statements


class IndependentComputationExchange(AnalyzedStrategy):
    strategy_id = "SS1"
    node_types = {"block"}

    def __init__(self, max_distance=1, allow_updates=True, **kwargs):
        super().__init__(**kwargs)
        if max_distance < 1:
            raise ValueError("max_distance must be positive")
        self.max_distance = max_distance
        self.allow_updates = allow_updates

    def analyze_site(self, ctx, block):
        sequence = statements(block)
        candidates = []
        for i, left in enumerate(sequence):
            if not computational(ctx, left):
                continue
            if (
                not self.allow_updates
                and left.named_children[0].type == "update_expression"
            ):
                continue
            a = ctx.effects(left)
            for distance in range(1, min(self.max_distance, len(sequence) - i - 1) + 1):
                right = sequence[i + distance]
                if not computational(ctx, right):
                    if ctx.effects(right).reasons:
                        break
                    continue
                b = ctx.effects(right)
                middle = sequence[i + 1 : i + distance]
                if not a.independent(b) or any(
                    not a.independent(ctx.effects(s))
                    or not b.independent(ctx.effects(s))
                    for s in middle
                ):
                    ctx.reject(
                        left,
                        "computation_dependency",
                        other_start=right.start_byte,
                        left_reads=sorted(a.reads),
                        left_writes=sorted(a.writes),
                        right_reads=sorted(b.reads),
                        right_writes=sorted(b.writes),
                    )
                    continue
                candidates.append(
                    Candidate(
                        left,
                        [
                            ctx.edit(left, ctx.text(right)),
                            ctx.edit(right, ctx.text(left)),
                        ],
                        "independent_computations",
                        {"distance": distance},
                    )
                )
        return candidates
