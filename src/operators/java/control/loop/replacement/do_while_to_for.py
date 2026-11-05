"""CL6: DoWhileToFor with checked lexical scopes and transfer targets."""
from operators.java.base.conversion import ConversionStrategy, CheckedConstruction


class DoWhileToFor(ConversionStrategy):
    strategy_id = "CL6"
    node_types = {"do_statement"}

    def analyze_site(self, ctx, node):
        from .do_while_to_while import DoWhileToWhile
        if node.parent.type == "labeled_statement":
            return self.reject(ctx, node, "labeled_do_for_not_supported")
        delegate = DoWhileToWhile(seed=self.seed)
        delegate.post_test_header = "for (;;)"
        candidates = delegate.analyze_site(ctx, node)
        for candidate in candidates:
            candidate.construction = "checked_post_test_for"
        return candidates


class _DoWhileToForConstructor(CheckedConstruction):
    def __init__(self):
        self.strategy_id = "CL6"
        super().__init__()


DoWhileToFor.constructor_type = _DoWhileToForConstructor
