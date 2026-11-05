"""SD2: RedundantDeclarationInsertion."""
from operators.java.statement.declaration.tools import InsertionStrategy


class RedundantDeclarationInsertion(InsertionStrategy):
    strategy_id = "SD2"

    def build_snippet(self, ctx, node, typ, name, value):
        return f"{typ} {name} = {value};", "unused_declaration"
