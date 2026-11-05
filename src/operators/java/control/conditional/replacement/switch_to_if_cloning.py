"""CC7: SwitchToIfCloning, preserving original bodies and lexical scopes."""
from operators.java.base.conversion import ConversionStrategy, CheckedConstruction
from operators.java.control.conditional.tools import construct_switch_if


class SwitchToIfCloning(ConversionStrategy):
    strategy_id = "CC7"
    node_types = {"switch_expression"}

    def analyze_site(self, ctx, node):
        return construct_switch_if(self, ctx, node, cloning=True)


from .switch_to_if_nesting import _SwitchToIfConstructor
SwitchToIfCloning.constructor_type = _SwitchToIfConstructor
SwitchToIfCloning.options = {"fallthrough_strategy": "cloning"}
