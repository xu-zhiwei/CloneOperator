"""C11 source context, lexical bindings and conservative scalar effects.

No preprocessing is performed. Translation units containing directives are
rejected because even identifiers from headers can be function-like macros.
Unsuffixed decimal constants are restricted to C11's guaranteed int range.
"""
from dataclasses import dataclass, field
from operators.base.results import Edit
from operators.tools.source import walk, ancestor, unwrap

LOOPS = {"for_statement", "while_statement", "do_statement"}
COMMENTS = {"comment"}
INT_MIN, INT_MAX = -32767, 32767


def contains(outer, inner):
    return outer.start_byte <= inner.start_byte and inner.end_byte <= outer.end_byte


def statements(block):
    return [n for n in block.named_children if n.type not in COMMENTS]


@dataclass(eq=False)
class Symbol:
    name: str
    node: object
    declaration: object
    scope: object
    initializer: object = None
    supported: bool = False
    parameter: bool = False
    escaped: bool = False

    @property
    def key(self):
        return self.node.start_byte


@dataclass
class Effects:
    reads: set = field(default_factory=set)
    writes: set = field(default_factory=set)
    safe: bool = True

    def merge(self, other):
        return Effects(
            self.reads | other.reads,
            self.writes | other.writes,
            self.safe and other.safe,
        )

    def independent(self, other):
        return (
            self.safe
            and other.safe
            and not (
                self.writes & (other.reads | other.writes) or other.writes & self.reads
            )
        )


class CContext:
    function_type = "function_definition"

    def __init__(self, code, parser):
        self.source = code.encode("utf-8")
        self.tree = parser.parse(self.source)
        self.nodes = list(walk(self.tree.root_node))
        self.methods = [n for n in self.nodes if n.type == self.function_type]
        self.rejections = []
        self.preprocessed = any(n.type.startswith("preproc_") for n in self.nodes)
        self.symbols = []
        self._refs = {}
        if self.tree.root_node.has_error:
            return
        self._collect_symbols()
        self._refs = {s.key: [] for s in self.symbols}
        declarations = {s.node.id for s in self.symbols}
        for n in self.nodes:
            if n.type == "identifier" and n.id not in declarations and self.is_reference(n):
                s = self.resolve(n)
                if s:
                    self._refs[s.key].append(n)
                    p = n.parent
                    while p is not None and p.type == "parenthesized_expression":
                        p = p.parent
                    if (
                        p is not None
                        and p.type == "pointer_expression"
                        and self.op(p) == "&"
                    ):
                        s.escaped = True

    def text(self, node):
        return (
            self.source[node.start_byte : node.end_byte].decode("utf-8") if node else ""
        )

    def op(self, node):
        return self.text(node.child_by_field_name("operator"))

    def edit(self, node, replacement):
        return Edit(node.start_byte, node.end_byte, replacement)

    def reject(self, node, reason, **details):
        self.rejections.append(
            dict(
                reason=reason,
                start_byte=node.start_byte,
                end_byte=node.end_byte,
                **details
            )
        )

    def alternative(self, node):
        clause = node.child_by_field_name("alternative")
        return (
            clause.named_children[-1]
            if clause is not None and clause.type == "else_clause"
            else clause
        )

    def function(self, node):
        return ancestor(node, self.function_type)

    def fresh(self, node, prefix="sctTemp"):
        # Also avoid global identifiers, including names that could be captured.
        names = {
            self.text(n)
            for n in self.nodes
            if n.type in {"identifier", "type_identifier", "field_identifier"}
        }
        index = 0
        while prefix + str(index) in names:
            index += 1
        return prefix + str(index)

    def _collect_symbols(self):
        for n in self.nodes:
            if n.type not in {
                "declaration",
                "parameter_declaration",
            } or not self.function(n):
                continue
            parameter = n.type == "parameter_declaration"
            if parameter:
                function_declarator = next(
                    (
                        d
                        for d in walk(
                            self.function(n).child_by_field_name("declarator")
                        )
                        if d.type == "function_declarator"
                    ),
                    None,
                )
                if ancestor(n, "function_declarator") != function_declarator:
                    # Parameter names inside callback types or local prototypes
                    # have prototype scope, not the enclosing function's scope.
                    continue
            declarators = n.children_by_field_name("declarator")
            qualifiers = any(
                c.type
                in {"type_qualifier", "storage_class_specifier", "attribute_specifier"}
                for c in n.named_children
            )
            good_type = (
                self.text(n.child_by_field_name("type")) == "int" and not qualifiers
            )
            scope = (
                self.function(n)
                if parameter
                else ancestor(n.parent, "compound_statement")
            )
            # The for-init declaration is visible only within its loop.
            if n.parent.type == "for_statement":
                scope = n.parent
            for d in declarators:
                value = (
                    d.child_by_field_name("value")
                    if d.type == "init_declarator"
                    else None
                )
                name = (
                    d.child_by_field_name("declarator")
                    if d.type == "init_declarator"
                    else d
                )
                ids = [x for x in walk(name) if x.type == "identifier"]
                if not ids:
                    continue
                name_node = ids[0]
                simple = name.type == "identifier"
                self.symbols.append(
                    Symbol(
                        self.text(name_node),
                        name_node,
                        n,
                        scope,
                        value,
                        good_type and simple and len(declarators) == 1,
                        parameter,
                    )
                )

    @staticmethod
    def is_reference(node):
        parent = node.parent
        if parent is None:
            return False
        # C has separate label/member/tag namespaces. Declarator identifiers
        # (especially a function named like one of its parameters) are not reads.
        if parent.type in {"enumerator", "function_declarator", "parameter_declaration", "declaration", "init_declarator"}:
            if parent.child_by_field_name("declarator") == node or parent.child_by_field_name("name") == node:
                return False
        return True

    def resolve(self, node):
        name = self.text(node)
        candidates = [
            s
            for s in self.symbols
            if s.name == name
            and s.scope
            and contains(s.scope, node)
            and (s.parameter or s.node.start_byte <= node.start_byte)
        ]
        return min(
            candidates,
            key=lambda s: (s.scope.end_byte - s.scope.start_byte, -s.node.start_byte),
            default=None,
        )

    def binding(self, node):
        node = unwrap(node)
        if node is None or node.type != "identifier":
            return None
        s = self.resolve(node)
        return s if s and s.supported and not s.escaped else None

    def references_of(self, symbol):
        return self._refs[symbol.key]

    def initialized(self, symbol, at):
        if symbol.parameter:
            return True
        if symbol.initializer is not None:
            return at.start_byte > symbol.initializer.end_byte
        # Only a preceding direct assignment in the same block establishes
        # initialization here. Complex data flow deliberately remains unknown.
        block = symbol.declaration.parent
        direct = at
        while direct and direct.parent != block:
            direct = direct.parent
        if direct is None:
            return False
        for st in statements(block):
            if st.start_byte >= direct.start_byte:
                break
            info = self.assignment(st, require_initialized=False)
            if info and info[0] is symbol and self.op(info[2]) == "=":
                return True
        return False

    def integer(self, node):
        node = unwrap(node)
        if node is None:
            return None
        if node.type == "unary_expression" and self.op(node) in {"+", "-"}:
            arg = node.child_by_field_name("argument")
            value = self.integer(arg)
            return (
                (-value if self.op(node) == "-" else value)
                if value is not None
                else None
            )
        if node.type != "number_literal":
            return None
        text = self.text(node)
        digits = text[1:] if text.startswith(("-", "+")) else text
        if (
            not digits.isascii()
            or not digits.isdecimal()
            or len(digits) > 1
            and digits.startswith("0")
        ):
            return None
        value = int(text)
        return value if INT_MIN <= value <= INT_MAX else None

    def effects(self, node, require_initialized=True):
        node = unwrap(node)
        if node is None:
            return Effects(safe=False)
        if self.integer(node) is not None:
            return Effects()
        if node.type == "identifier":
            s = self.binding(node)
            if not s or require_initialized and not self.initialized(s, node):
                return Effects(safe=False)
            return Effects(reads={s.key})
        if node.type == "binary_expression" and self.op(node) in {
            "+",
            "-",
            "*",
            "<",
            "<=",
            ">",
            ">=",
            "==",
            "!=",
            "&&",
            "||",
            "&",
            "|",
            "^",
        }:
            return self.effects(
                node.child_by_field_name("left"), require_initialized
            ).merge(
                self.effects(node.child_by_field_name("right"), require_initialized)
            )
        if node.type == "unary_expression" and self.op(node) in {"!", "+", "-"}:
            return self.effects(
                node.child_by_field_name("argument"), require_initialized
            )
        return Effects(safe=False)

    def pure(self, node):
        e = self.effects(node)
        return e.safe and not e.writes

    def constant(self, node):
        node = unwrap(node)
        value = self.integer(node)
        if value is not None:
            return value
        if node is None:
            return None
        if node.type == "unary_expression" and self.op(node) == "!":
            v = self.constant(node.child_by_field_name("argument"))
            return int(not v) if v is not None else None
        if node.type != "binary_expression":
            return None
        a = self.constant(node.child_by_field_name("left"))
        b = self.constant(node.child_by_field_name("right"))
        if a is None or b is None:
            return None
        op = self.op(node)
        actions = {
            "+": lambda: a + b,
            "-": lambda: a - b,
            "*": lambda: a * b,
            "<": lambda: int(a < b),
            "<=": lambda: int(a <= b),
            ">": lambda: int(a > b),
            ">=": lambda: int(a >= b),
            "==": lambda: int(a == b),
            "!=": lambda: int(a != b),
            "&&": lambda: int(bool(a) and bool(b)),
            "||": lambda: int(bool(a) or bool(b)),
            "&": lambda: a & b,
            "|": lambda: a | b,
            "^": lambda: a ^ b,
        }
        if op not in actions:
            return None
        result = actions[op]()
        return result if INT_MIN <= result <= INT_MAX else None

    def total(self, node):
        """Removing a computation additionally requires no possible signed UB."""
        node = unwrap(node)
        if not self.pure(node):
            return False
        if self.constant(node) is not None or node.type == "identifier":
            return True
        if node.type == "unary_expression":
            return self.op(node) in {"!", "+"} and self.total(
                node.child_by_field_name("argument")
            )
        if node.type == "binary_expression":
            op = self.op(node)
            l, r = node.child_by_field_name("left"), node.child_by_field_name("right")
            if op in {"+", "-"} and self.constant(r) == 0:
                return self.total(l)
            return (
                op in {"<", "<=", ">", ">=", "==", "!=", "&&", "||", "&", "|", "^"}
                and self.total(l)
                and self.total(r)
            )
        return False

    def declaration(self, node):
        if node.type != "declaration" or node.parent.type != "compound_statement":
            return None
        syms = [s for s in self.symbols if s.declaration == node]
        return (
            syms[0]
            if len(syms) == 1 and syms[0].supported and not syms[0].escaped
            else None
        )

    def assignment(self, statement, require_initialized=True):
        if (
            statement.type != "expression_statement"
            or len(statement.named_children) != 1
        ):
            return None
        expr = statement.named_children[0]
        if expr.type != "assignment_expression":
            return None
        lhs, rhs = expr.child_by_field_name("left"), expr.child_by_field_name("right")
        symbol = self.binding(lhs)
        if not symbol or not self.effects(rhs, require_initialized).safe:
            return None
        if (
            self.op(expr) != "="
            and require_initialized
            and not self.initialized(symbol, lhs)
        ):
            return None
        return symbol, rhs, expr

    def assignment_effects(self, statement):
        info = self.assignment(statement)
        if not info or self.op(info[2]) != "=":
            return Effects(safe=False)
        return self.effects(info[1]).merge(Effects(writes={info[0].key}))
