"""CL2: RedundantLoopRemoval."""
from operators.java.control.loop.tools import LoopStrategy
from operators.java.control.conditional.tools import checked_exception_risk
from operators.java.analysis.semantic import contains, statements


class RedundantLoopRemoval(LoopStrategy):
    strategy_id = "CL2"
    node_types = {"while_statement", "for_statement"}

    def __init__(self, max_definition_distance=4, **kwargs):
        super().__init__(**kwargs)
        if max_definition_distance < 1:
            raise ValueError("max_definition_distance must be positive")
        self.max_definition_distance = max_definition_distance

    def analyze_site(self, ctx, node):
        condition = node.child_by_field_name("condition")
        body = node.child_by_field_name("body")
        if condition is None or body is None:
            return []
        if checked_exception_risk(body):
            return self.reject(ctx, body, "removal_may_invalidate_checked_catch")
        if not ctx.effects(condition).pure:
            return self.reject(ctx, condition, "zero_iteration_condition_has_effects")
        if node.type == "for_statement":
            init = node.child_by_field_name("init")
            symbols = ctx.declaration_symbols(init) if init else []
            if len(symbols) != 1 or symbols[0] is None:
                return self.reject(ctx, node, "for_initializer_not_isolated_local")
            symbol = symbols[0]
            value = (
                ctx.constant_value(symbol.initializer) if symbol.initializer else None
            )
            if value is None or not ctx.effects(symbol.initializer).pure:
                return self.reject(ctx, node, "for_initial_value_unknown")
            if ctx.constant_value(condition, {symbol.key: value}) is not False:
                return self.reject(ctx, node, "loop_not_proven_zero_iteration")
            return [self.accept(ctx, node, "{ }", "remove_zero_iteration_for")]
        if node.parent.type != "block":
            return self.reject(ctx, node, "while_definition_not_in_same_block")
        sequence = statements(node.parent)
        index = sequence.index(node)
        reads = ctx.effects(condition).reads
        environment = {}
        definitions = []
        for previous in reversed(
            sequence[max(0, index - self.max_definition_distance) : index]
        ):
            effects = ctx.effects(previous)
            if effects.reasons or effects.writes & reads:
                break
            for symbol in ctx.declaration_symbols(previous):
                if symbol and symbol.key in reads and symbol.initializer is not None:
                    value = ctx.constant_value(symbol.initializer)
                    if value is not None and ctx.effects(symbol.initializer).pure:
                        environment[symbol.key] = value
                        definitions.append(symbol)
        if ctx.constant_value(condition, environment) is not False:
            return self.reject(ctx, node, "loop_not_proven_zero_iteration")
        target = node
        if (
            len(sequence) == 2
            and index == 1
            and len(definitions) == 1
            and sequence[0] == definitions[0].declaration.parent
        ):
            if all(
                contains(node.parent, r) for r in ctx.references_of(definitions[0])
            ) and not ctx.captured_or_unresolved(definitions[0]):
                target = node.parent
        return [
            self.accept(
                ctx,
                target,
                "{ }",
                "remove_zero_iteration_while",
                initial_values={str(k): v for k, v in environment.items()},
            )
        ]
