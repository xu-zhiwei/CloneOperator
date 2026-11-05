"""Single-edit application, parsing rollback and instance random state."""
import random
from operators.base.results import ApplicationResult


class Strategy:
    strategy_id = ""
    language = "java"

    @property
    def semantic_contract(self):
        from operators.base.contracts import get_contract
        return get_contract(self.strategy_id, self.language)

    @property
    def relation(self):
        from operators.taxonomy import get_relation
        return get_relation(self.strategy_id)

    def make_context(self, code):
        from operators.java.analysis.semantic import SemanticContext

        return SemanticContext(code, self.parser)

    def __init__(self, seed=42):
        self.seed = seed
        from operators.base.language import make_parser

        self.parser = make_parser(self.language)
        self.rng = random.Random(seed)
        self.last_result = None

    def __call__(self, code, k=1):
        return self.apply(code, k).code

    def candidates(self, ctx):
        raise NotImplementedError

    def apply(self, code, k=1):
        if not isinstance(code, str):
            raise TypeError("SCT expects a UTF-8 Python string")
        if isinstance(k, bool) or not isinstance(k, int) or k < 0:
            raise ValueError("k must be a nonnegative integer")
        result = ApplicationResult(code, self.strategy_id, k, language=self.language)
        rng = random.Random(self.seed)
        self.rng = rng
        for _ in range(k):
            ctx = self.make_context(result.code)
            if ctx.tree.root_node.has_error:
                result.rejections.append({"reason": "input_parse_error"})
                break
            if self.language == "java" and not ctx.translation_safe:
                result.rejections.append({"reason": "java_lexical_translation_not_supported"})
                break
            candidates = list(self.candidates(ctx))
            result.rejections.extend(ctx.rejections)
            result.eligible_candidates += len(candidates)
            if not candidates:
                result.rejections.append(
                    {
                        "reason": "no_safe_site",
                        "detail": "No site satisfies the documented type, binding and structural restrictions.",
                    }
                )
                break
            ratio = getattr(self, "site_ratio", 1.0)
            if ratio < 1:
                candidates = rng.sample(
                    candidates, max(1, int(len(candidates) * ratio))
                )
            selection = getattr(self, "selection", "random")
            if selection == "random":
                rng.shuffle(candidates)
            elif selection == "last":
                candidates.reverse()
            accepted = False
            for edits in candidates:
                edits = sorted(edits, key=lambda e: e.start_byte)
                if any(a.end_byte > b.start_byte for a, b in zip(edits, edits[1:])):
                    raise ValueError("overlapping SCT edits")
                source = ctx.source
                for e in reversed(edits):
                    source = (
                        source[: e.start_byte]
                        + e.replacement.encode("utf-8")
                        + source[e.end_byte :]
                    )
                if source == ctx.source:
                    continue
                if self.language == "java":
                    from operators.java.analysis.context import lexing_supported
                    if not lexing_supported(source):
                        result.rejections.append({"reason": "output_java_lexical_translation_not_supported"})
                        continue
                if self.parser.parse(source).root_node.has_error:
                    result.rejections.append(
                        {
                            "reason": "output_parse_error",
                            "start_byte": edits[0].start_byte,
                        }
                    )
                    continue
                result.code = source.decode("utf-8")
                result.successful += 1
                candidate = next(
                    (
                        x
                        for x in getattr(self, "last_candidates", [])
                        if sorted(x.edits, key=lambda e: e.start_byte) == edits
                    ),
                    None,
                )
                result.changes.append(
                    {
                        "application": result.successful,
                        "semantic_contract": self.strategy_id,
                        "family_id": self.relation.family_id,
                        "inverse_id": self.relation.inverse_id,
                        "direction": self.relation.direction,
                        "validation": "candidate_checks_and_parse_only",
                        "construction": candidate.construction
                        if candidate
                        else self.strategy_id,
                        "metadata": candidate.metadata if candidate else {},
                        "edits": [
                            {
                                "start_byte": e.start_byte,
                                "end_byte": e.end_byte,
                                "before": ctx.source[e.start_byte : e.end_byte].decode(
                                    "utf-8"
                                ),
                                "after": e.replacement,
                            }
                            for e in edits
                        ],
                    }
                )
                accepted = True
                break
            if not accepted:
                break
        self.last_result = result
        return result
