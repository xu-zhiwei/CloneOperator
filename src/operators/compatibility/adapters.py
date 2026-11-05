"""Public historical signatures adapted to current strategies and shared tools.

Algorithms live in the strategies and tools. Version names share the current
implementation rather than retaining separate historical algorithms.
"""
from random import Random
from operators.base.strategy import Strategy
from operators.registry import create_strategy
from operators.tools.literals import LiteralCandidates, NeutralLiteralCandidates
from operators.tools.sampling import FragmentSampler
from operators.tools.resources import statistics_path

BaseOperator = Strategy


class Adapter:
    """Common string/bytes round-trip and historical multi-round convention."""

    def __call__(self, code, k=1):
        if isinstance(k, bool) or not isinstance(k, int) or k < 0:
            raise ValueError("k must be a nonnegative integer")
        result = code
        for _ in range(k):
            result = self.operate(result)
            if isinstance(result, tuple):
                result = result[0]
        return result

    @staticmethod
    def decode(code):
        binary = isinstance(code, (bytes, bytearray))
        return (bytes(code).decode("utf-8") if binary else code), binary

    @staticmethod
    def encode(code, binary):
        return code.encode("utf-8") if binary else code


class ConstantReplace(Adapter):
    def __init__(
        self,
        token_vocab=None,
        max_numeric_depth=4,
        max_numeric_atoms=12,
        max_string_candidates=32,
    ):
        self.engine = LiteralCandidates(
            token_vocab, max_numeric_depth, max_numeric_atoms, max_string_candidates
        )

    def __getattr__(self, name):
        return getattr(self.engine, name)

    def operate(self, code):
        source, binary = self.decode(code)
        data = bytearray(source.encode("utf-8"))
        constants = self.engine.identify_constants(self.engine._parse_code(data), data)
        recommendations = self.engine.recommend_replacements(constants)
        result = self.engine.apply_replacements(data, recommendations).decode("utf-8")
        return self.encode(result, binary), recommendations


class RedundantConstantInsert(ConstantReplace):
    def __init__(self, token_vocab=None, seed=42, factor=1):
        self.engine = NeutralLiteralCandidates(token_vocab, seed, factor)


class ConstantReplaceV2(ConstantReplace):
    def __init__(
        self,
        token_vocab=None,
        max_numeric_depth=4,
        max_numeric_atoms=12,
        max_string_candidates=32,
        sample_one_constant_per_statement=False,
        seed=42,
    ):
        super().__init__(
            token_vocab, max_numeric_depth, max_numeric_atoms, max_string_candidates
        )
        self.sample_one_constant_per_statement = sample_one_constant_per_statement
        self.random = Random(seed)

    def operate(self, code):
        # V2 name is retained; all versions use the current typed candidate engine.
        if not self.sample_one_constant_per_statement:
            return super().operate(code)
        from operators.tools.literals import select_per_statement

        source, binary = self.decode(code)
        data = bytearray(source.encode())
        tree = self.engine._parse_code(data)
        constants = select_per_statement(
            tree, self.engine.identify_constants(tree, data), self.random
        )
        recommendations = self.engine.recommend_replacements(constants)
        return (
            self.encode(
                self.engine.apply_replacements(data, recommendations).decode(), binary
            ),
            recommendations,
        )


class IdentifierRenameV4(Adapter):
    def __init__(
        self,
        token_vocab=None,
        model_name="microsoft/codebert-base",
        word_len=3,
        top_k_syn=0.5,
        rename_similarity=0.5,
        whitening_kernel_size=256,
        seed=42,
        *,
        name_selector=None
    ):
        from operators.tools.names import ModelNameSelector

        self.selector = name_selector or ModelNameSelector(
            token_vocab,
            model_name,
            word_len,
            top_k_syn,
            rename_similarity,
            whitening_kernel_size,
            seed,
        )
        self.operator = create_strategy(
            "WI1", candidate_source="fresh", name_selector=self.selector, seed=seed
        )

    def operate(self, code):
        source, binary = self.decode(code)
        from operators.analysis.semantic import SemanticContext
        from types import SimpleNamespace

        ctx = SemanticContext(source, self.operator.parser)
        names = sorted(
            {
                symbol.name
                for symbol in ctx.symbols
                if not ctx.captured_or_unresolved(symbol)
            }
        )
        recommendations = self.selector.recommend(names) if names else {}
        original_selector = self.operator.name_selector
        self.operator.name_selector = SimpleNamespace(
            recommend=lambda names: {
                name: recommendations[name] for name in names if name in recommendations
            }
        )
        try:
            result = self.operator.apply(source, k=len(names))
        finally:
            self.operator.name_selector = original_selector
        applied = {
            c["metadata"]["original_name"]: (
                c["metadata"]["replacement_name"],
                c["metadata"]["score"],
            )
            for c in result.changes
        }
        return self.encode(result.code, binary), applied


class IdentifierRenameV1(IdentifierRenameV4):
    def __init__(
        self,
        token_vocab=None,
        model_name="microsoft/codebert-base",
        rename_ratio=0.2,
        rename_similarity=None,
        seed=42,
    ):
        if not 0 <= rename_ratio <= 1:
            raise ValueError("rename_ratio must be in [0,1]")
        super().__init__(
            token_vocab=token_vocab,
            model_name=model_name,
            rename_similarity=0.5 if rename_similarity is None else rename_similarity,
            seed=seed,
        )
        self.rename_ratio = rename_ratio
        if rename_ratio:
            self.operator.site_ratio = rename_ratio

    def operate(self, code):
        return super().operate(code) if self.rename_ratio else (code, {})


# Same current selector and signature, no independent version algorithms.
IdentifierRenameV2 = IdentifierRenameV4
IdentifierRenameV3 = IdentifierRenameV4


class IdentifierRenameV5(IdentifierRenameV4):
    def __init__(
        self,
        token_vocab=None,
        model_name="microsoft/codebert-base",
        num_return_sequences=5,
        num_beams=5,
        max_length=5,
        seed=42,
    ):
        # Historical generation controls map to a bounded current candidate pool.
        super().__init__(token_vocab=token_vocab, model_name=model_name, seed=seed)
        self.operator.max_candidates = max(1, num_return_sequences)
        self.num_beams, self.max_length = num_beams, max_length


class IdentifierReorder(Adapter):
    def __init__(self, reorder_ratio=1.0, seed=42):
        if not 0 <= reorder_ratio <= 1:
            raise ValueError("reorder_ratio must be in [0,1]")
        self.reorder_ratio = reorder_ratio
        self.operator = create_strategy(
            "SE1", site_ratio=reorder_ratio or 1.0, seed=seed
        )

    def operate(self, code):
        source, binary = self.decode(code)
        result = self.operator.transform_disjoint(source, ratio=self.reorder_ratio)
        return self.encode(result, binary)


class StatementReorder(Adapter):
    def __init__(self, seed=42, max_swaps=20, mode="all", enabled_reorders=None):
        if mode not in {"all", "single"} or max_swaps < 0:
            raise ValueError("Invalid declaration reorder configuration")
        if isinstance(enabled_reorders, str):
            enabled_reorders = [
                part.strip() for part in enabled_reorders.split(",") if part.strip()
            ]
        supported = set(create_strategy("SD1").enabled_reorders)
        parsed = set(enabled_reorders or supported)
        selected = parsed & supported
        if parsed - supported and selected:
            import warnings

            warnings.warn(
                "Ignoring unknown reorder rules: " + repr(parsed - supported),
                UserWarning,
            )
        options = {"enabled_reorders": selected or supported}
        self.operator = create_strategy("SD1", seed=seed, **options)
        self.mode, self.max_swaps = mode, max_swaps

    def operate(self, code):
        source, binary = self.decode(code)
        result = (
            self.operator(source, k=min(1, self.max_swaps))
            if self.mode == "single"
            else self.operator.transform_disjoint(source, limit=self.max_swaps)
        )
        return self.encode(result, binary)

    def transform_statement_reorder(self, source):
        return self.operate(source)


class RedundantStatementInsert(Adapter):
    def __init__(
        self,
        insert_ratio=1.0,
        seed=42,
        analyzer_mode="random",
        type_sampling="random",
        name_sampling="random",
        init_sampling="random",
        stats_path=None,
        stats_scope="BigCloneBench",
    ):
        if analyzer_mode not in {"random", "def_only", "def_use", "inc_dec", "dec_inc"}:
            raise ValueError("Unsupported analyzer_mode: " + analyzer_mode)
        self.rng = Random(seed)
        self.analyzer_mode = analyzer_mode
        self.options = dict(insert_ratio=insert_ratio, seed=seed)
        self.sampling = dict(
            stats_path=stats_path or str(statistics_path()),
            stats_scope=stats_scope,
            type_sampling=type_sampling,
            name_sampling=name_sampling,
            init_sampling=init_sampling,
        )
        # Validate before use, including statistics scope and sampling modes.
        self.sampler = FragmentSampler(**self.sampling)
        if not 0 < insert_ratio <= 1:
            raise ValueError("insert_ratio must be in (0,1]")

    def operate(self, code):
        source, binary = self.decode(code)
        mode = (
            self.rng.choice(("def_only", "def_use", "inc_dec", "dec_inc"))
            if self.analyzer_mode == "random"
            else self.analyzer_mode
        )
        operator = create_strategy(
            "SD2" if mode == "def_only" else "SS2",
            **self.options,
            **({} if mode == "def_only" else {"modes": (mode,)})
        )
        operator.sampler = FragmentSampler(
            **self.sampling, numeric_only=mode in {"inc_dec", "dec_inc"}
        )
        return self.encode(operator(source), binary)


class ConversionAdapter(Adapter):
    modes = {}

    def __init__(self, mode="random", seed=42, min_case_count=1):
        if mode != "random" and mode not in self.modes:
            raise ValueError("Unknown conversion mode: " + mode)
        self.mode, self.seed = mode, seed
        self.operators = {
            name: create_strategy(sid, min_case_count=min_case_count).operator()
            for name, sid in self.modes.items()
        }

    def available_modes(self, source):
        return tuple(self.modes)

    def operate(self, code):
        source, binary = self.decode(code)
        modes = self.available_modes(source)
        if not modes:
            return code
        mode = self.mode
        if mode == "random":
            mode = Random(self.seed).choice(modes)
            self.seed += 1
        return self.encode(self.operators[mode](source), binary)


class LoopReplace(ConversionAdapter):
    modes = {
        "for_to_while": "CL3",
        "for_to_dowhile": "CL5",
        "while_to_for": "CL4",
        "dowhile_to_for": "CL6",
    }

    def __init__(self, mode="random", seed=42):
        super().__init__(mode, seed)


class ConditionReplace(ConversionAdapter):
    modes = {
        "if_to_switch_nesting": "CC4",
        "if_to_switch_cloning": "CC5",
        "switch_to_if_nesting": "CC6",
        "switch_to_if_cloning": "CC7",
    }

    def available_modes(self, source):
        from operators.base.construction import ConstructionBase
        from operators.tools.source import walk

        tree = ConstructionBase()._parse_code(source.encode())
        types = {n.type for n in walk(tree.root_node)}
        return tuple(
            name
            for name in self.modes
            if name.startswith("if_to_")
            and "if_statement" in types
            or name.startswith("switch_to_")
            and types & {"switch_expression", "switch_statement"}
        )

    def _get_avaiable_modes(self, code):
        return list(self.available_modes(code))

# Name used by the original public release.
IdentifierRename = IdentifierRenameV4
