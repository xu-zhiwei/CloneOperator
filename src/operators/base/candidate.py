"""Candidate pipeline shared by concrete strategies."""
from dataclasses import dataclass, field
from operators.base.strategy import Strategy
from operators.tools.source import ancestor


@dataclass
class Candidate:
    node: object
    edits: list
    construction: str
    metadata: dict = field(default_factory=dict)


class AnalyzedStrategy(Strategy):
    """Each strategy implements a separately inspectable candidate pipeline."""

    node_types = frozenset()

    def __init__(self, seed=42, selection="random", site_ratio=1.0):
        super().__init__(seed=seed)
        if selection not in {"random", "first", "last"}:
            raise ValueError("selection must be random, first or last")
        if not 0 < site_ratio <= 1:
            raise ValueError("site_ratio must be in (0, 1]")
        self.selection = selection
        self.site_ratio = site_ratio
        self.last_candidates = []

    def identify_sites(self, ctx):
        if self.language == "java" and not ctx.translation_safe:
            ctx.reject(ctx.tree.root_node, "java_lexical_translation_not_supported")
            return
        for node in ctx.nodes:
            if (
                node.type in self.node_types
                and (not hasattr(ctx, "owns_site") or ctx.owns_site(node))
                and ancestor(node, getattr(ctx, "function_type", "method_declaration"))
                is not None
            ):
                yield node

    def analyze_site(self, ctx, node):
        raise NotImplementedError

    def candidates(self, ctx):
        candidates = []
        for site in self.identify_sites(ctx):
            candidates.extend(self.analyze_site(ctx, site))
        self.last_candidates = candidates
        for candidate in candidates:
            yield candidate.edits

    def transform_disjoint(self, code, limit=None, ratio=1.0):
        """Compatibility batch: each source region is changed at most once.

        Default apply/code strength semantics remain single-site and unchanged.
        """
        from random import Random
        from operators.tools.editing import apply_disjoint_edits

        if not 0 <= ratio <= 1 or limit is not None and limit < 0:
            raise ValueError("Invalid batch selection configuration")
        if ratio == 0 or limit == 0:
            return code
        self.rng = Random(self.seed)
        ctx = self.make_context(code)
        if ctx.tree.root_node.has_error:
            return code
        if self.language == "java" and not ctx.translation_safe:
            return code
        list(self.candidates(ctx))
        if self.strategy_id not in {"SE1", "SD1", "SS1", "CC1"}:
            # Independently analyzed insertions/extractions may choose identical
            # fresh names. Reparse and regenerate every scope-changing edit.
            count = max(1, int(len(self.last_candidates) * ratio)) if self.last_candidates else 0
            if limit is not None:
                count = min(count, limit)
            return self.apply(code, k=count).code
        candidates = list(self.last_candidates)
        if not candidates:
            return code
        self.rng.shuffle(candidates)
        count = max(1, int(len(candidates) * ratio))
        if limit is not None:
            count = min(count, limit)
        return apply_disjoint_edits(ctx.source, candidates, count, self.parser)

    @staticmethod
    def accept(ctx, node, replacement, construction, **metadata):
        return Candidate(node, [ctx.edit(node, replacement)], construction, metadata)

    @staticmethod
    def reject(ctx, node, reason, **details):
        ctx.reject(node, reason, **details)
        return []

    @staticmethod
    def validate_modes(value, allowed):
        modes = {value} if isinstance(value, str) else set(value)
        if not modes or modes - set(allowed):
            raise ValueError(
                f"Expected nonempty subset of {sorted(allowed)}, got {value!r}"
            )
        return tuple(sorted(modes))
