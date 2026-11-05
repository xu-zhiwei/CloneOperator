"""WC5: IntegerSubtractionRepresentation."""
from operators.java.word.constant.tools import IntegerLiteralStrategy


class IntegerSubtractionRepresentation(IntegerLiteralStrategy):
    strategy_id = "WC5"

    def __init__(self, offsets=(1, 2, 4), **kwargs):
        super().__init__(**kwargs)
        if not offsets or any(
            isinstance(x, bool) or not isinstance(x, int) or x <= 0 for x in offsets
        ):
            raise ValueError("offsets must be positive integers")
        self.offsets = tuple(sorted(set(offsets)))

    def analyze_site(self, ctx, node):
        literal = self.literal(ctx, node)
        if literal is None:
            return []
        value, suffix = literal
        limit = 2 ** 63 - 1 if suffix else 2 ** 31 - 1
        candidates = [
            self.accept(
                ctx,
                node,
                f"({value+offset}{suffix} - {offset}{suffix})",
                "integer_subtraction",
                offset=offset,
            )
            for offset in self.offsets
            if value + offset <= limit
        ]
        return candidates or self.reject(ctx, node, "subtraction_operand_out_of_range")
