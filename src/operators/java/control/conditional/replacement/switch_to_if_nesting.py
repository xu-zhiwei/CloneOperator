"""CC6: SwitchToIfNesting, preserving original bodies and lexical scopes."""
from operators.java.base.conversion import ConversionStrategy, CheckedConstruction
from operators.java.control.conditional.tools import construct_switch_if


class SwitchToIfNesting(ConversionStrategy):
    strategy_id = "CC6"
    node_types = {"switch_expression"}

    def analyze_site(self, ctx, node):
        return construct_switch_if(self, ctx, node, cloning=False)


class _SwitchToIfConstructor(CheckedConstruction):
    def __init__(self, fallthrough_strategy="nesting"):
        if fallthrough_strategy not in {"nesting", "cloning"}:
            raise ValueError("Unknown fallthrough_strategy")
        self.strategy_id = "CC6" if fallthrough_strategy == "nesting" else "CC7"
        super().__init__()


SwitchToIfNesting.constructor_type = _SwitchToIfConstructor
