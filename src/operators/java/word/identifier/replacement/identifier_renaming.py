"""WI1: IdentifierRenaming."""
from operators.java.tools.resources import statistics_path
from operators.base.candidate import AnalyzedStrategy, Candidate
from operators.java.tools.sampling import TypedSampler, load_statistics
from operators.tools.source import walk


class IdentifierRenaming(AnalyzedStrategy):
    strategy_id = "WI1"
    node_types = {
        "variable_declarator",
        "formal_parameter",
        "spread_parameter",
        "catch_formal_parameter",
    }

    def __init__(
        self,
        candidate_source="common",
        name_selector=None,
        token_vocab=None,
        stats_path=None,
        stats_scope="overall",
        name_sampling="frequency",
        ranker=None,
        min_similarity=None,
        max_candidates=16,
        **kwargs
    ):
        super().__init__(**kwargs)
        if candidate_source not in {"common", "vocabulary", "fresh", "ranked"}:
            raise ValueError("Unknown identifier candidate source")
        if candidate_source == "vocabulary" and not token_vocab:
            raise ValueError("vocabulary mode requires token_vocab")
        if candidate_source == "ranked" and ranker is None:
            raise ValueError("ranked mode requires an explicit similarity ranker")
        if (
            name_sampling not in {"frequency", "inverse_frequency", "random"}
            or max_candidates < 1
        ):
            raise ValueError("Invalid name sampling configuration")
        if min_similarity is not None and (
            ranker is None or not -1 <= min_similarity <= 1
        ):
            raise ValueError("min_similarity requires a ranker and must be in [-1,1]")
        self.name_selector = name_selector
        self.candidate_source = candidate_source
        self.vocabulary = tuple(token_vocab or ())
        if (
            stats_path is None
            and name_sampling != "random"
            and candidate_source in {"common", "vocabulary"}
        ):
            stats_path = statistics_path()
        self.statistics = (
            load_statistics(str(stats_path), stats_scope) if stats_path else {}
        )
        self.name_sampling = name_sampling
        self.ranker = ranker
        self.min_similarity = min_similarity
        self.max_candidates = max_candidates

    def recommend_names(self, ctx, symbol):
        if self.name_selector is not None:
            recommendation = self.name_selector.recommend([symbol.name]).get(
                symbol.name
            )
            if recommendation is None:
                return []
            new, score = recommendation
            existing = {
                ctx.text(n)
                for n in walk(symbol.method)
                if n.type in {"identifier", "type_identifier"}
            }
            return (
                [(new, score)]
                if TypedSampler.valid_name(new) and new not in existing
                else []
            )
        existing = {
            ctx.text(n)
            for n in walk(symbol.method)
            if n.type in {"identifier", "type_identifier"}
        }
        if self.candidate_source == "fresh":
            return [(ctx.fresh(symbol.name_node, "sctName"), None)]
        frequencies = self.statistics.get("variable_name_frequency_by_type", {}).get(
            symbol.java_type, {}
        )
        pool = (
            self.vocabulary
            if self.candidate_source in {"vocabulary", "ranked"}
            else (list(frequencies) or TypedSampler.NAMES)
        )
        names = sorted(
            {n for n in pool if TypedSampler.valid_name(n) and n not in existing}
        )
        if not names:
            return [(ctx.fresh(symbol.name_node, "value"), None)]
        if self.ranker:
            scores = list(self.ranker(symbol.name, names))
            if len(scores) != len(names):
                raise ValueError("ranker must return one score per candidate name")
            ranked = sorted(zip(names, scores), key=lambda x: (-float(x[1]), x[0]))
            return [
                (n, float(score))
                for n, score in ranked
                if self.min_similarity is None or score >= self.min_similarity
            ][: self.max_candidates]
        chosen = []
        while names and len(chosen) < self.max_candidates:
            name = TypedSampler.weighted_pick(
                self.rng, names, frequencies, self.name_sampling
            )
            chosen.append((name, None))
            names.remove(name)
        return chosen

    def analyze_site(self, ctx, node):
        name = node.child_by_field_name("name")
        symbol = ctx.symbol_for_name(name) if name else None
        if symbol is None:
            return self.reject(ctx, node, "unresolved_rename_declaration")
        if ctx.captured_or_unresolved(symbol) or ctx.resolve(name) is not symbol:
            return self.reject(ctx, node, "rename_has_capture_or_ambiguous_binding")
        references = ctx.references_of(symbol)
        recommendations = self.recommend_names(ctx, symbol)
        if not recommendations:
            return self.reject(ctx, node, "no_name_passes_similarity_threshold")
        return [
            Candidate(
                node,
                [ctx.edit(n, new) for n in [name] + references],
                "binding_preserving_rename",
                {
                    "original_name": symbol.name,
                    "replacement_name": new,
                    "java_type": symbol.java_type,
                    "source": self.candidate_source,
                    "score": score,
                },
            )
            for new, score in recommendations
        ]
