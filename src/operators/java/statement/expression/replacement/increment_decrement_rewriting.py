"""SE5: IncrementDecrementRewriting."""
from operators.base.candidate import AnalyzedStrategy


class IncrementDecrementRewriting(AnalyzedStrategy):
    strategy_id = "SE5"
    node_types = {"update_expression"}

    def __init__(self, mode="assignment", **kwargs):
        super().__init__(**kwargs)
        if mode not in {"assignment", "compound"}:
            raise ValueError("mode must be assignment or compound")
        self.mode = mode

    def analyze_site(self, ctx, node):
        if node.parent.type != "expression_statement":
            return self.reject(ctx, node, "update_value_is_observed")
        name = node.named_children[0]
        symbol = ctx.resolve(name)
        if symbol is None or symbol.final or symbol.java_type not in {"int", "long"}:
            return self.reject(ctx, node, "unsupported_update_binding")
        sign = "+" if "++" in ctx.text(node) else "-"
        one = "1L" if symbol.java_type == "long" else "1"
        replacement = (
            f"{symbol.name} {sign}= {one}"
            if self.mode == "compound"
            else f"{symbol.name} = {symbol.name} {sign} {one}"
        )
        return [
            self.accept(ctx, node, replacement, self.mode, java_type=symbol.java_type)
        ]
