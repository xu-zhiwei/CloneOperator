"""C candidate pipeline and language-specific analysis hook."""
from operators.base.candidate import AnalyzedStrategy
from operators.c.analysis.context import CContext
from operators.tools.source import walk


class CStrategy(AnalyzedStrategy):
    language = "c"

    def make_context(self, code):
        return CContext(code, self.parser)

    def identify_sites(self, ctx):
        # Translation phases precede parsing. Do not treat hidden line splices,
        # C11 trigraphs or source-position macros as ordinary parsed tokens.
        import re
        if (b"\\u" in ctx.source or b"\\U" in ctx.source or re.search(rb"\?\?[=/'()!<>-]", ctx.source)
                or re.search(rb"\\[ \t]*(?:\r\n?|\n)", ctx.source)
                or any(token in ctx.source for token in (b"<%", b"%>", b"<:", b":>", b"%:"))
                or any(n.type == "identifier" and ctx.text(n) in {
                    "__LINE__", "__FILE__", "__DATE__", "__TIME__", "__TIMESTAMP__", "__COUNTER__"
                } for n in ctx.nodes)):
            ctx.reject(ctx.tree.root_node, "unsupported_c_translation_context")
            return
        if ctx.preprocessed:
            ctx.reject(ctx.tree.root_node, "unresolved_preprocessor_context")
            return
        if any(
            n.type
            in {
                "gnu_asm_expression",
                "asm_statement",
                "attribute_specifier",
                "ms_declspec_modifier",
                "seh_try_statement",
                "extension_expression",
            }
            for n in ctx.nodes
        ):
            ctx.reject(ctx.tree.root_node, "unsupported_c_extension")
            return
        if any(
            n.type == "compound_statement"
            and n.parent is not None
            and n.parent.type == "parenthesized_expression"
            or n.type == "function_definition"
            and n.parent.type != "translation_unit"
            or n.type == "typeof_specifier"
            for n in ctx.nodes
        ):
            ctx.reject(ctx.tree.root_node, "unsupported_c_extension")
            return
        # Experimental v2: eligibility is decided by each operator at its site.
        # Presence of an array/record elsewhere in the function is not a veto.
        yield from super().identify_sites(ctx)

    def function_safe(self, ctx, node):
        fn = ctx.function(node)
        # These four existing constructions insert fresh isolated locals at
        # function entry; they neither move existing declarations nor rewrite
        # array accesses. Retain all original checks for scope-changing rules.
        if self.strategy_id in {"SD2", "SS2", "CC2", "CL1"}:
            return not any(n.type in {"asm_statement", "gnu_asm_expression", "seh_try_statement"}
                           for n in walk(fn))
        if any(
            n.type
            in {
                "goto_statement",
                "labeled_statement",
                "seh_try_statement",
                "asm_statement",
            }
            for n in walk(fn)
        ):
            return False
        if any(
            n.type == "identifier"
            and ctx.text(n) in {"setjmp", "longjmp", "sigsetjmp", "siglongjmp"}
            for n in walk(fn)
        ):
            return False
        # VLA, qualifiers and opaque declarations make scope-changing rewrites unsafe.
        return not any(
            n.type in {"array_declarator", "type_qualifier", "attribute_specifier"}
            for n in walk(fn)
        )

    def rvalue(self, ctx, node):
        """Only positions known to read an int value; never declarators/lvalues."""
        p = node.parent
        while p and p.type == "parenthesized_expression":
            node, p = p, p.parent
        if p is None:
            return False
        if p.type == "assignment_expression":
            return p.child_by_field_name("right") == node
        if p.type == "init_declarator":
            return p.child_by_field_name("value") == node
        return p.type in {"return_statement", "binary_expression", "unary_expression"}

    def safe_literal(self, ctx, node):
        """Exclude declarators, case labels, sizeof and other unevaluated contexts."""
        if ctx.integer(node) is None or not self.rvalue(ctx, node):
            return False
        current = node.parent
        while current and current != ctx.function(node):
            if current.type in {
                "sizeof_expression",
                "alignof_expression",
                "case_statement",
                "array_declarator",
                "generic_expression",
            }:
                return False
            current = current.parent
        return True

    def adjacent(self, ctx, block):
        from operators.c.analysis.context import statements

        items = statements(block)
        return zip(items, items[1:])
