"""CC5: IfToSwitchCloning, preserving original bodies and lexical scopes."""
from operators.java.base.conversion import ConversionStrategy, CheckedConstruction
from operators.java.control.conditional.tools import construct_if_switch


class IfToSwitchCloning(ConversionStrategy):
    strategy_id = "CC5"
    node_types = {"if_statement"}

    def analyze_site(self, ctx, node):
        return construct_if_switch(self, ctx, node, cloning=True)


from .if_to_switch_nesting import _IfToSwitchConstructor
IfToSwitchCloning.constructor_type = _IfToSwitchConstructor
IfToSwitchCloning.options = {"multi_case_strategy": "cloning"}
