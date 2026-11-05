"""SS2: RedundantComputationInsertion."""
from operators.java.statement.declaration.tools import InsertionStrategy


class RedundantComputationInsertion(InsertionStrategy):
    strategy_id = "SS2"

    def __init__(self, modes=("def_use", "inc_dec", "dec_inc"), **kwargs):
        kwargs.setdefault("java_types", ("int", "long"))
        super().__init__(**kwargs)
        self.modes = self.validate_modes(modes, {"def_use", "inc_dec", "dec_inc"})
        if set(self.sampler.java_types) - {"int", "long"}:
            raise ValueError("Computation insertion requires int or long")

    def build_snippet(self, ctx, node, typ, name, value):
        mode = self.rng.choice(self.modes)
        if mode == "def_use":
            body = f"{name} = {value};"
        elif mode == "inc_dec":
            body = f"{name}++; {name}--;"
        else:
            body = f"{name}--; {name}++;"
        return f"{{ {typ} {name} = {value}; {body} }}", mode
