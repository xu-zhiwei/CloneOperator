"""Shared analysis and construction helpers for this target."""
from operators.base.candidate import AnalyzedStrategy, Candidate
from operators.java.tools.sampling import TypedSampler
from operators.tools.editing import direct_block
from operators.java.analysis.semantic import INTEGRAL, PRIMITIVES
from operators.base.results import Edit


def safe_initializer(ctx, symbol):
    node = symbol.initializer
    if node is None:
        return True
    if symbol.java_type in PRIMITIVES:
        typ = ctx.expression_type(node)
        if symbol.java_type == "boolean":
            return typ == "boolean" and ctx.effects(node).pure
        if symbol.java_type == "long":
            return typ in INTEGRAL and ctx.effects(node).pure
        if symbol.java_type == "int":
            return typ in INTEGRAL - {"long"} and ctx.effects(node).pure
        # Narrow types are supported only for literal initializers whose value
        # is representable, avoiding loss of Java constant-narrowing context.
        literal = ctx.integer(node)
        limits = {"byte": (-128, 127), "short": (-32768, 32767), "char": (0, 65535)}
        return bool(
            literal
            and symbol.java_type in limits
            and limits[symbol.java_type][0] <= literal[0] <= limits[symbol.java_type][1]
        )
    return node.type in {"null_literal", "string_literal"} and symbol.java_type in {
        "String",
        "Object",
    }


class DeclarationStrategy(AnalyzedStrategy):
    node_types = {"local_variable_declaration"}

    def analyze_declaration(
        self, ctx, node, allow_final=False, allow_multiple=True, require_pure=True
    ):
        if not direct_block(node):
            ctx.reject(node, "declaration_not_in_ordinary_block")
            return None
        symbols = ctx.declaration_symbols(node)
        if not symbols or any(s is None for s in symbols):
            ctx.reject(node, "unresolved_declaration")
            return None
        if not allow_multiple and len(symbols) > 1:
            ctx.reject(node, "multiple_declarators_disabled")
            return None
        if any(s.final and not allow_final or s.modifiers - {"final"} for s in symbols):
            ctx.reject(node, "declaration_modifiers_not_supported")
            return None
        if require_pure and any(not safe_initializer(ctx, s) for s in symbols):
            ctx.reject(
                node, "unsafe_initializer", effects=sorted(ctx.effects(node).reasons)
            )
            return None
        return symbols


class InsertionStrategy(AnalyzedStrategy):
    node_types = {"block"}

    def __init__(
        self,
        java_types=("int", "long", "boolean"),
        stats_path=None,
        stats_scope="overall",
        type_sampling="random",
        name_sampling="random",
        init_sampling="random",
        method_entry_only=False,
        insert_ratio=None,
        **kwargs,
    ):
        if insert_ratio is not None:
            kwargs["site_ratio"] = insert_ratio
        super().__init__(**kwargs)
        self.method_entry_only = method_entry_only
        self.sampler = TypedSampler(
            java_types,
            stats_path,
            stats_scope,
            type_sampling,
            name_sampling,
            init_sampling,
        )

    def identify_sites(self, ctx):
        seen = set()
        for block, _ in ctx.insertion_sites(self.method_entry_only):
            if block.id not in seen:
                seen.add(block.id)
                yield block

    def analyze_site(self, ctx, node):
        result = []
        for block, position in ctx.insertion_sites(self.method_entry_only):
            if block != node:
                continue
            typ, name, value = self.sampler.sample(ctx, node, self.rng)
            snippet, mode = self.build_snippet(ctx, node, typ, name, value)
            result.append(
                Candidate(
                    node,
                    [Edit(position, position, "\n" + snippet + "\n")],
                    mode,
                    {
                        "java_type": typ,
                        "name": name,
                        "initializer": value,
                        "position": position,
                    },
                )
            )
        return result

    def build_snippet(self, ctx, node, typ, name, value):
        raise NotImplementedError
