"""Typed statistical sampling without shared random state."""
from functools import lru_cache
import json
import re
from pathlib import Path
from operators.java.tools.resources import statistics_path


@lru_cache(maxsize=8)
def load_statistics(path, scope):
    with Path(path).open(encoding="utf-8") as stream:
        payload = json.load(stream)
    if scope == "overall":
        return payload["overall"]
    try:
        return payload["datasets"][scope]
    except KeyError:
        raise ValueError(f"Unknown statistics scope: {scope}") from None


class TypedSampler:
    """Reuse the original type/name/initializer frequency schema, without globals."""

    DEFAULTS = {
        "int": "0",
        "long": "0L",
        "boolean": "false",
        "String": "null",
        "Object": "null",
    }
    NAMES = ("value", "count", "index", "result", "tmp", "flag", "done")
    KEYWORDS = set(
        "abstract assert boolean break byte case catch char class const continue default do double else enum extends final finally float for goto if implements import instanceof int interface long native new package private protected public return short static strictfp super switch synchronized this throw throws transient try void volatile while true false null var record yield".split()
    )
    KEYWORDS.add("_")

    def __init__(
        self,
        java_types=("int", "long", "boolean"),
        stats_path=None,
        stats_scope="overall",
        type_sampling="random",
        name_sampling="random",
        init_sampling="random",
    ):
        self.java_types = tuple(java_types)
        if not self.java_types or set(self.java_types) - self.DEFAULTS.keys():
            raise ValueError("Unsupported insertion types")
        for mode in (type_sampling, name_sampling, init_sampling):
            if mode not in {"random", "frequency", "inverse_frequency"}:
                raise ValueError("Unknown sampling mode: " + mode)
        self.type_sampling, self.name_sampling, self.init_sampling = (
            type_sampling,
            name_sampling,
            init_sampling,
        )
        if stats_path is None and any(
            mode != "random" for mode in (type_sampling, name_sampling, init_sampling)
        ):
            stats_path = statistics_path()
        self.stats = (
            load_statistics(str(Path(stats_path).resolve()), stats_scope)
            if stats_path
            else {}
        )

    @staticmethod
    def weighted_pick(rng, values, frequencies, mode):
        values = sorted(values)
        if not values:
            raise ValueError("No safe sampling candidates")
        if mode == "random":
            return rng.choice(values)
        weights = [max(1, frequencies.get(v, 1)) for v in values]
        if mode == "inverse_frequency":
            weights = [1 / w for w in weights]
        return rng.choices(values, weights=weights, k=1)[0]

    @classmethod
    def valid_name(cls, name):
        return (
            bool(re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", name))
            and name not in cls.KEYWORDS
        )

    @staticmethod
    def valid_initializer(text, java_type):
        if java_type == "boolean":
            return text in {"true", "false"}
        if java_type in {"String", "Object"}:
            return text == "null"
        suffix = "L" if java_type == "long" else ""
        if not re.fullmatch(r"-?(?:0|[1-9][0-9]*)" + ("[lL]" if suffix else ""), text):
            return False
        value = int(text[:-1] if suffix else text)
        bits = 64 if suffix else 32
        return -(2 ** (bits - 1)) <= value < 2 ** (bits - 1)

    def sample(self, ctx, site, rng, java_type=None):
        typ = java_type or self.weighted_pick(
            rng,
            self.java_types,
            self.stats.get("variable_type_frequency", {}),
            self.type_sampling,
        )
        name_frequencies = self.stats.get("variable_name_frequency_by_type", {}).get(
            typ, {}
        )
        names = [n for n in name_frequencies if self.valid_name(n)] or list(self.NAMES)
        base = self.weighted_pick(rng, names, name_frequencies, self.name_sampling)
        name = ctx.fresh(site, base)
        initializers = self.stats.get("variable_init_value_frequency_by_type", {}).get(
            typ, {}
        )
        values = [v for v in initializers if self.valid_initializer(v, typ)] or [
            self.DEFAULTS[typ]
        ]
        value = self.weighted_pick(rng, values, initializers, self.init_sampling)
        return typ, name, value


class FragmentSampler(TypedSampler):
    """Type-matched literal sampling for configurable declaration fragments.

    Supports the existing insertion interface's primitive types and string
    literals; standard SCT sampling keeps its narrower defaults unchanged.
    """

    DEFAULTS = {
        **TypedSampler.DEFAULTS,
        "byte": "0",
        "short": "0",
        "char": "'a'",
        "float": "0.0f",
        "double": "0.0",
    }

    def __init__(self, *args, numeric_only=False, **kwargs):
        kwargs.setdefault("java_types", tuple(self.DEFAULTS))
        super().__init__(*args, **kwargs)
        available = (
            set(self.stats.get("variable_type_frequency", {})) & self.DEFAULTS.keys()
        )
        self.java_types = tuple(sorted(available or self.java_types))
        if numeric_only:
            self.java_types = tuple(
                t for t in self.java_types if t not in {"boolean", "String", "Object"}
            ) or ("int",)

    @staticmethod
    def valid_initializer(text, java_type):
        if "\\u" in text:
            return False
        from tree_sitter import Language, Parser
        import tree_sitter_java

        parser = Parser(Language(tree_sitter_java.language()))
        tree = parser.parse(("class T{Object v=" + text + ";}").encode())
        if tree.root_node.has_error:
            return False
        from operators.tools.source import walk

        forbidden = {
            "method_invocation",
            "object_creation_expression",
            "assignment_expression",
            "update_expression",
            "field_access",
            "array_access",
            "identifier",
        }
        # The artificial declaration contributes T and v; inspect initializer only.
        declarator = next(
            (n for n in walk(tree.root_node) if n.type == "variable_declarator"), None
        )
        value = declarator.child_by_field_name("value") if declarator else None
        return value is not None and not any(n.type in forbidden for n in walk(value))

    @staticmethod
    def coerce(text, java_type):
        value = text.strip()
        if java_type == "boolean":
            return value if value in {"true", "false"} else "false"
        if java_type in {"String", "Object"}:
            return (
                value
                if value == "null" or value.startswith('"') and value.endswith('"')
                else "null"
            )
        if java_type == "char":
            return value if value.startswith("'") and value.endswith("'") else "'a'"
        numeric = re.fullmatch(r"[+-]?\d+(?:\.\d+(?:[eE][+-]?\d+)?)?[lLfFdD]?", value)
        if not numeric:
            return FragmentSampler.DEFAULTS[java_type]
        base = value.rstrip("lLfFdD")
        if java_type in {"int", "long", "byte", "short"}:
            if not re.fullmatch(r"[+-]?\d+", base):
                return FragmentSampler.DEFAULTS[java_type]
            limits = {
                "byte": (-128, 127),
                "short": (-32768, 32767),
                "int": (-(2 ** 31), 2 ** 31 - 1),
                "long": (-(2 ** 63), 2 ** 63 - 1),
            }
            lo, hi = limits[java_type]
            if not lo <= int(base) <= hi:
                return FragmentSampler.DEFAULTS[java_type]
            return base + ("L" if java_type == "long" else "")
        return base + ("f" if java_type == "float" else "")

    def sample(self, ctx, site, rng, java_type=None):
        from operators.tools.source import ancestor, walk

        typ = java_type or self.weighted_pick(
            rng,
            self.java_types,
            self.stats.get("variable_type_frequency", {}),
            self.type_sampling,
        )
        frequencies = self.stats.get("variable_name_frequency_by_type", {}).get(
            typ, self.stats.get("variable_name_frequency", {})
        )
        names = [name for name in frequencies if self.valid_name(name)] or list(
            self.NAMES
        )
        name = self.weighted_pick(rng, names, frequencies, self.name_sampling)
        method = ancestor(site, "method_declaration") or site
        existing = {
            ctx.text(n)
            for n in walk(method)
            if n.type in {"identifier", "type_identifier"}
        }
        if name in existing:
            name = ctx.fresh(site, name)
        initializers = self.stats.get("variable_init_value_frequency_by_type", {}).get(
            typ, self.stats.get("variable_init_value_frequency", {})
        )
        values = [v for v in initializers if self.valid_initializer(v, typ)] or [
            self.DEFAULTS[typ]
        ]
        value = self.weighted_pick(rng, values, initializers, self.init_sampling)
        return typ, name, self.coerce(value, typ)
