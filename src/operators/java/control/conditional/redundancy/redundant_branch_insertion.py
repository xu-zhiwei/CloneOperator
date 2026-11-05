"""CC2: RedundantBranchInsertion."""
from operators.java.statement.declaration.tools import InsertionStrategy


class RedundantBranchInsertion(InsertionStrategy):
    strategy_id = "CC2"

    def __init__(self, modes=("if_false", "dead_else"), **kwargs):
        super().__init__(**kwargs)
        self.modes = self.validate_modes(modes, {"if_false", "dead_else"})

    def build_snippet(self, ctx, node, typ, name, value):
        mode = self.rng.choice(self.modes)
        dead = f"{{ {typ} {name} = {value}; }}"
        return (
            (
                f"if (false) {dead}"
                if mode == "if_false"
                else f"if (true) {{ }} else {dead}"
            ),
            mode,
        )
