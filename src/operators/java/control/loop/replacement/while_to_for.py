"""CL4: WhileToFor with checked lexical scopes and transfer targets."""
from operators.java.base.conversion import ConversionStrategy, CheckedConstruction
from operators.java.control.loop.tools import LoopStrategy, checked_for_conversion


class WhileToFor(ConversionStrategy):
    strategy_id = "CL4"
    node_types = {"while_statement"}

    def analyze_site(self, ctx, node):
        if node.parent.type == "labeled_statement" or LoopStrategy.analyze_structure(self, ctx, node) is None:
            return self.reject(ctx, node, "loop_pattern_or_capture")
        condition = node.child_by_field_name("condition")
        body = node.child_by_field_name("body")
        return [self.accept(ctx, node, "for (; " + ctx.text(condition) + "; ) {\n" + ctx.text(body) + "\n}", "checked_while_for")]



class _WhileToForConstructor(CheckedConstruction):
    def __init__(self):
        self.strategy_id = "CL4"
        super().__init__()


WhileToFor.constructor_type = _WhileToForConstructor
