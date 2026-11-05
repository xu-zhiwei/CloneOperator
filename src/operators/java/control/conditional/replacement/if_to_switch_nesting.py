"""CC4: IfToSwitchNesting, preserving original bodies and lexical scopes."""
from operators.java.base.conversion import ConversionStrategy, CheckedConstruction
from operators.java.control.conditional.tools import construct_if_switch


class IfToSwitchNesting(ConversionStrategy):
    strategy_id = "CC4"
    node_types = {"if_statement"}

    def analyze_site(self, ctx, node):
        return construct_if_switch(self, ctx, node, cloning=False)


class _IfToSwitchConstructor(CheckedConstruction):
    def __init__(self, multi_case_strategy="nesting", min_case_count=1):
        if multi_case_strategy not in {"nesting", "cloning"}:
            raise ValueError("Unknown multi_case_strategy")
        self.strategy_id = "CC4" if multi_case_strategy == "nesting" else "CC5"
        super().__init__(min_case_count=min_case_count)


IfToSwitchNesting.constructor_type = _IfToSwitchConstructor
