"""WC3: IntegerAdditionDecomposition."""
from operators.java.word.constant.tools import IntegerLiteralStrategy


class IntegerAdditionDecomposition(IntegerLiteralStrategy):
    strategy_id = "WC3"

    def __init__(self, mode="balanced", **kwargs):
        super().__init__(**kwargs)
        if mode not in {"balanced", "random"}:
            raise ValueError("mode must be balanced or random")
        self.mode = mode

    def analyze_site(self, ctx, node):
        literal = self.literal(ctx, node)
        if literal is None:
            return []
        value, suffix = literal
        if abs(value) < 2:
            return self.reject(ctx, node, "no_nontrivial_addition_decomposition")
        first = (
            abs(value) // 2
            if self.mode == "balanced"
            else self.rng.randrange(1, abs(value))
        )
        first = first if value > 0 else -first
        second = value - first
        return [
            self.accept(ctx, node, f"({first}{suffix} + {second}{suffix})", self.mode)
        ]
