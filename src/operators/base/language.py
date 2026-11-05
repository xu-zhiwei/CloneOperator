"""Lazy grammar selection. Missing C support never prevents Java imports."""
from tree_sitter import Language, Parser


def make_parser(language):
    if language == "java":
        import tree_sitter_java as grammar
    elif language == "c":
        try:
            import tree_sitter_c as grammar
        except ImportError as exc:
            raise RuntimeError(
                "C mode requires tree_sitter_c==0.24.1; install the declared C dependency."
            ) from exc
    else:
        raise ValueError(f"Unknown SCT language: {language!r}")
    return Parser(Language(grammar.language()))
