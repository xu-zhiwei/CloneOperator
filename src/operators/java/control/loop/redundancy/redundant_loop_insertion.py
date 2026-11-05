"""CL1: RedundantLoopInsertion."""
from operators.java.statement.declaration.tools import InsertionStrategy


class RedundantLoopInsertion(InsertionStrategy):
    strategy_id = "CL1"

    def __init__(self, modes=("while", "for"), **kwargs):
        super().__init__(**kwargs)
        self.modes = self.validate_modes(modes, {"while", "for"})

    def build_snippet(self, ctx, node, typ, name, value):
        mode = self.rng.choice(self.modes)
        if mode == "while":
            flag = ctx.fresh(node, "active")
            if flag == name:
                flag = ctx.fresh(node, "loopActive")
            snippet = f"{{ boolean {flag}=false; while ({flag}) {{ {typ} {name}={value}; }} }}"
        else:
            index = ctx.fresh(node, "index")
            if index == name:
                index = ctx.fresh(node, "loopIndex")
            snippet = (
                f"for (int {index}=0; {index}<0; {index}++) {{ {typ} {name}={value}; }}"
            )
        return snippet, "zero_iteration_" + mode
