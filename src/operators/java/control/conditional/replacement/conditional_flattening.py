"""CC9: ConditionalFlattening."""
from operators.java.control.conditional.tools import ConditionalStrategy
from operators.java.analysis.semantic import statements


class ConditionalFlattening(ConditionalStrategy):
    strategy_id = "CC9"

    def __init__(self, max_depth=8, **kwargs):
        super().__init__(**kwargs)
        if max_depth < 2:
            raise ValueError("max_depth must be at least two")
        self.max_depth = max_depth

    def analyze_site(self, ctx, node):
        current = node
        conditions = []
        while len(conditions) < self.max_depth:
            if current.child_by_field_name("alternative") is not None:
                break
            condition = self.ordinary_condition(ctx, current)
            if condition is None:
                return []
            conditions.append(ctx.text(condition))
            body = current.child_by_field_name("consequence")
            children = statements(body) if body.type == "block" else [body]
            if len(children) != 1 or children[0].type != "if_statement":
                break
            current = children[0]
        if len(conditions) < 2:
            return self.reject(ctx, node, "not_a_flattenable_conditional_chain")
        # If the next inner if has an else, preserve it inside the merged body.
        expression = " && ".join("(" + c + ")" for c in conditions)
        return [
            self.accept(
                ctx,
                node,
                f"if ({expression}) {{ {ctx.text(body)} }}",
                "flatten_short_circuit_chain",
                depth=len(conditions),
            )
        ]
