"""CL5: ForToDoWhile with checked lexical scopes and transfer targets."""
from operators.java.base.conversion import ConversionStrategy, CheckedConstruction
from operators.java.control.loop.tools import LoopStrategy, checked_for_conversion


class ForToDoWhile(ConversionStrategy):
    strategy_id = "CL5"
    node_types = {"for_statement"}

    def analyze_site(self, ctx, node):
        return checked_for_conversion(self, ctx, node, do_while=True)


class _ForToDoWhileConstructor(CheckedConstruction):
    def __init__(self):
        self.strategy_id = "CL5"
        super().__init__()


ForToDoWhile.constructor_type = _ForToDoWhileConstructor
