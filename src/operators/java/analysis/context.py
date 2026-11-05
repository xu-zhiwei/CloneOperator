"""Parsed source context and UTF-8 offsets."""
from operators.tools.source import walk, unwrap, ancestor
from operators.base.results import Edit
import unicodedata


def lexing_supported(source):
    """Reject translations/name equivalences not implemented by this lexer.

    Java ignores FORMAT and certain control characters in identifier equality.
    Comparing raw Tree-sitter spellings would miss those aliases. Reject them
    conservatively even in comments/literals until full lexical translation is
    implemented, while retaining ordinary UTF-8 names and Chinese comments.
    """
    if b"\\u" in source:
        return False
    return not any(unicodedata.category(ch) == "Cf" or ord(ch) <= 8
                   or 14 <= ord(ch) <= 27 or 127 <= ord(ch) <= 159
                   for ch in source.decode("utf-8"))


class Context:
    def __init__(self, code, parser):
        self.source = code.encode("utf-8")
        self.translation_safe = lexing_supported(self.source)
        self.tree = parser.parse(self.source)
        self.nodes = list(walk(self.tree.root_node))
        self.methods = [n for n in self.nodes if n.type == "method_declaration"]

    def text(self, node):
        return self.source[node.start_byte : node.end_byte].decode("utf-8")

    def op(self, node):
        value = node.child_by_field_name("operator")
        return self.text(value) if value else ""

    def edit(self, node, replacement):
        return Edit(node.start_byte, node.end_byte, replacement)

    def fresh(self, node, prefix="sctTemp"):
        method = ancestor(node, "method_declaration") or node
        names = {
            self.text(n)
            for n in walk(method)
            if n.type in {"identifier", "type_identifier"}
        }
        i = 0
        while f"{prefix}{i}" in names:
            i += 1
        return f"{prefix}{i}"

    def integer(self, node):
        node = unwrap(node)
        if node is None or node.type != "decimal_integer_literal":
            return None
        text = self.text(node).replace("_", "")
        suffix = "L" if text[-1:] in {"l", "L"} else ""
        digits = text[:-1] if suffix else text
        # A leading zero is octal in Java, despite this grammar node's name.
        if not digits.isdecimal() or (len(digits) > 1 and digits.startswith("0")):
            return None
        value = int(digits)
        if value > (2 ** 63 - 1 if suffix else 2 ** 31 - 1):
            return None
        return value, suffix
