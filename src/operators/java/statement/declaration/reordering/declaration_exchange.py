"""SD1: DeclarationExchange."""
from operators.base.candidate import Candidate
from operators.java.statement.declaration.tools import DeclarationStrategy
from operators.java.analysis.semantic import statements


class DeclarationExchange(DeclarationStrategy):
    strategy_id = "SD1"

    def __init__(
        self,
        enabled_reorders=(
            "adjacent_single_decl_init",
            "adjacent_single_decl_optional_init",
            "adjacent_multi_decl",
            "non_adjacent_decl_run",
        ),
        max_distance=8,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.enabled_reorders = self.validate_modes(
            enabled_reorders,
            {
                "adjacent_single_decl_init",
                "adjacent_single_decl_optional_init",
                "adjacent_multi_decl",
                "non_adjacent_decl_run",
            },
        )
        if max_distance < 1:
            raise ValueError("max_distance must be positive")
        self.max_distance = max_distance

    def analyze_site(self, ctx, node):
        left = self.analyze_declaration(ctx, node, allow_final=True)
        if left is None:
            return []
        block = statements(node.parent)
        index = block.index(node)
        candidates = []
        for distance in range(1, min(self.max_distance, len(block) - index - 1) + 1):
            other = block[index + distance]
            if other.type != "local_variable_declaration":
                break
            if distance > 1 and "non_adjacent_decl_run" not in self.enabled_reorders:
                break
            right = self.analyze_declaration(ctx, other, allow_final=True)
            if right is None:
                continue
            multiple = len(left) > 1 or len(right) > 1
            missing = any(s.initializer is None for s in left + right)
            if multiple and "adjacent_multi_decl" not in self.enabled_reorders:
                continue
            if (
                missing
                and "adjacent_single_decl_optional_init" not in self.enabled_reorders
            ):
                continue
            middle = block[index + 1 : index + distance]
            effects_a, effects_b = ctx.effects(node), ctx.effects(other)
            if not effects_a.independent(effects_b) or any(
                not effects_a.independent(ctx.effects(s))
                or not effects_b.independent(ctx.effects(s))
                for s in middle
            ):
                ctx.reject(node, "declaration_dependency", other_start=other.start_byte)
                continue
            candidates.append(
                Candidate(
                    node,
                    [ctx.edit(node, ctx.text(other)), ctx.edit(other, ctx.text(node))],
                    "non_adjacent_decl_run"
                    if distance > 1
                    else "adjacent_declarations",
                    {"distance": distance},
                )
            )
        return candidates
