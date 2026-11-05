"""CL3: ForToWhile with checked lexical scopes and transfer targets."""
from operators.java.base.conversion import ConversionStrategy, CheckedConstruction
from operators.java.control.loop.tools import LoopStrategy, checked_for_conversion


class ForToWhile(ConversionStrategy):
    strategy_id = "CL3"
    node_types = {"for_statement"}

    def analyze_site(self, ctx, node):
        return checked_for_conversion(self, ctx, node, do_while=False)


class _ForToWhileConstructor(CheckedConstruction):
    def __init__(self):
        self.strategy_id = "CL3"
        super().__init__()


ForToWhile.constructor_type = _ForToWhileConstructor
