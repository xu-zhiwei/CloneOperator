"""CL8: WhileToDoWhile."""
from operators.java.control.loop.tools import LoopStrategy


class WhileToDoWhile(LoopStrategy):
    strategy_id = "CL8"
    node_types = {"while_statement"}

    def __init__(self, mode="guarded", **kwargs):
        super().__init__(**kwargs)
        if mode not in {"guarded", "condition_at_start"}:
            raise ValueError("mode must be guarded or condition_at_start")
        self.mode = mode

    def analyze_site(self, ctx, node):
        structure = self.analyze_structure(ctx, node)
        if structure is None:
            return []
        body, condition, labels, outer = structure
        prefix = "".join(label + ": " for label in labels)
        value = ctx.constant_value(condition)
        if value is None and self.unknown_constant_return_risk(ctx, node, condition):
            return self.reject(
                ctx, node, "external_constant_return_reachability_unknown"
            )
        if value is True:
            replacement = f"{prefix}do {{ {ctx.text(body)} }} while (true);"
            return [self.accept(ctx, outer, replacement, "constant_true_loop")]
        if value is False:
            # while(false) is normally rejected by javac as unreachable. Do
            # not turn a syntactically accepted invalid method into valid code.
            return self.reject(ctx, node, "compile_time_false_while")
        if self.mode == "condition_at_start":
            replacement = f"{prefix}do {{ if (!{ctx.text(condition)}) break; {ctx.text(body)} }} while (true);"
        else:
            replacement = f"if {ctx.text(condition)} {{ {prefix}do {{ {ctx.text(body)} }} while {ctx.text(condition)}; }}"
        # Preserve the original else binding when replacing an unbraced body.
        return [
            self.accept(ctx, outer, "{ " + replacement + " }", self.mode, labels=labels)
        ]
