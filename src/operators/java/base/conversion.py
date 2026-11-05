"""Structural strategies and historical constructors share the checked pipeline."""
from operators.base.candidate import AnalyzedStrategy


class CheckedConstruction:
    """Historical constructor interface; never bypass semantic candidate checks."""
    strategy_id = ""

    def __init__(self, **options):
        self.options = options

    def __call__(self, code):
        from operators.registry import create_strategy
        from operators.tools.source import walk
        op = create_strategy(self.strategy_id, **self.options)
        tree = op.parser.parse(code.encode("utf-8"))
        # All original sites may be considered, with reparsing after every edit.
        count = sum(n.type in op.node_types for n in walk(tree.root_node))
        return op(code, k=count)


class ConversionStrategy(AnalyzedStrategy):
    constructor_type = None
    options = {}

    def __init__(self, min_case_count=1, **kwargs):
        super().__init__(**kwargs)
        if min_case_count < 1:
            raise ValueError("min_case_count must be positive")
        self.min_case_count = min_case_count

    def operator(self):
        options = dict(self.options)
        if self.strategy_id in {"CC4", "CC5"}:
            options["min_case_count"] = self.min_case_count
        return self.constructor_type(**options)
