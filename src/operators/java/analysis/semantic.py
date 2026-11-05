"""Lexical bindings, Java primitive types and conservative effect summaries.

This is a method-local analysis, not a replacement for javac. Unknown symbols,
heap effects and captured bindings remain explicit barriers to transformations.
"""
from dataclasses import dataclass, field

from operators.java.analysis.context import Context
from operators.tools.source import ancestor, unwrap, walk

INTEGRAL = {"byte", "short", "char", "int", "long"}
NUMERIC = INTEGRAL | {"float", "double"}
PRIMITIVES = NUMERIC | {"boolean"}
BARRIERS = {
    "lambda_expression",
    "class_declaration",
    "interface_declaration",
    "enum_declaration",
    "record_declaration",
    "class_body",
}
COMMENTS = {"line_comment", "block_comment"}


def contains(outer, inner):
    return outer.start_byte <= inner.start_byte and inner.end_byte <= outer.end_byte


def statements(block):
    return [n for n in block.named_children if n.type not in COMMENTS]


@dataclass
class Symbol:
    name: str
    java_type: str
    declaration: object
    name_node: object
    scope: object
    method: object
    initializer: object = None
    modifiers: frozenset = frozenset()
    parameter: bool = False

    @property
    def key(self):
        return self.name_node.start_byte

    @property
    def final(self):
        return "final" in self.modifiers


@dataclass
class Effects:
    reads: set = field(default_factory=set)
    writes: set = field(default_factory=set)
    declarations: set = field(default_factory=set)
    reasons: set = field(default_factory=set)

    def merge(self, other):
        return Effects(
            self.reads | other.reads,
            self.writes | other.writes,
            self.declarations | other.declarations,
            self.reasons | other.reasons,
        )

    @property
    def pure(self):
        return not self.writes and not self.reasons

    def independent(self, other):
        return not (
            self.reasons
            or other.reasons
            or self.writes & (other.reads | other.writes)
            or other.writes & (self.reads | self.writes)
            or self.declarations & (other.reads | other.writes | other.declarations)
            or other.declarations & (self.reads | self.writes | self.declarations)
        )


class SemanticContext(Context):
    def __init__(self, code, parser):
        super().__init__(code, parser)
        self.rejections = []
        self._resolution = {}
        self._effects = {}
        self._types = {}
        self.symbols = self._collect_symbols()
        self.by_name = {}
        for symbol in self.symbols:
            self.by_name.setdefault(symbol.name, []).append(symbol)

    def reject(self, node, reason, **details):
        self.rejections.append(
            {
                "reason": reason,
                "start_byte": node.start_byte,
                "end_byte": node.end_byte,
                **details,
            }
        )

    @staticmethod
    def owns_site(node):
        current = node
        while current is not None:
            if current.type == "method_declaration":
                return True
            if current.type in BARRIERS | {"constructor_declaration", "compact_constructor_declaration"}:
                return False
            current = current.parent
        return False

    def _collect_symbols(self):
        symbols = []
        for node in self.nodes:
            method = ancestor(node, "method_declaration")
            # Never borrow an enclosing method across a constructor, lambda
            # or class initializer. Inner methods own their own symbols.
            if method is None or not self.owns_site(node):
                continue
            parameter = node.type in {
                "formal_parameter",
                "spread_parameter",
                "catch_formal_parameter",
            }
            if not parameter and node.type != "variable_declarator":
                continue
            name = node.child_by_field_name("name")
            holder = node if parameter else node.parent
            typ = holder.child_by_field_name("type")
            if name is None or typ is None:
                continue
            if not parameter and holder.type != "local_variable_declaration":
                continue
            if parameter:
                scope = (
                    method
                    if node.type != "catch_formal_parameter"
                    else ancestor(node, "catch_clause")
                )
            else:
                scope = holder.parent
                while scope and scope.type not in {
                    "block",
                    "for_statement",
                    "switch_block",
                    "try_with_resources_statement",
                }:
                    scope = scope.parent
            if scope is None:
                continue
            java_type = self.text(typ)
            for dimensions in node.named_children:
                if dimensions.type == "dimensions":
                    java_type += self.text(dimensions)
            if node.type == "spread_parameter":
                java_type += "[]"
            modifiers = set()
            for child in holder.named_children:
                if child.type == "modifiers":
                    modifiers.update(self.text(child).split())
            symbols.append(
                Symbol(
                    self.text(name),
                    java_type,
                    node,
                    name,
                    scope,
                    method,
                    node.child_by_field_name("value"),
                    frozenset(modifiers),
                    parameter,
                )
            )
        return symbols

    @staticmethod
    def is_reference(node):
        if node.type != "identifier" or node.parent is None:
            return False
        parent = node.parent
        name = parent.child_by_field_name("name")
        if name == node and parent.type in {
            "method_invocation",
            "method_declaration",
            "variable_declarator",
            "formal_parameter",
            "spread_parameter",
            "catch_formal_parameter",
            "class_declaration",
            "constructor_declaration",
            "enum_constant",
        }:
            return False
        if (
            parent.type == "field_access"
            and parent.child_by_field_name("field") == node
        ):
            return False
        if parent.type == "method_reference":
            return bool(parent.named_children) and parent.named_children[0] == node
        if parent.type in {
            "labeled_statement",
            "break_statement",
            "continue_statement",
        }:
            return False
        return True

    def resolve(self, node):
        if node is None or node.type != "identifier":
            return None
        if node.id in self._resolution:
            return self._resolution[node.id]
        method = ancestor(node, "method_declaration")
        matches = []
        for symbol in self.by_name.get(self.text(node), []):
            if symbol.method != method or not contains(symbol.scope, node):
                continue
            if not symbol.parameter and node.start_byte < symbol.name_node.start_byte:
                continue
            matches.append(symbol)
        # Java forbids redeclaration in overlapping local scopes. Reject such
        # malformed inputs instead of guessing which binding the user intended.
        if len(matches) == 1:
            result = matches[0]
            parent = node.parent
            while parent is not None and parent != method:
                if parent.type in BARRIERS:
                    result = None
                    break
                parent = parent.parent
            if not self.is_reference(node) and result.name_node != node:
                result = None
        else:
            result = None
        self._resolution[node.id] = result
        return result

    def symbol_for_name(self, node):
        return next((s for s in self.symbols if s.name_node == node), None)

    def references_of(self, symbol):
        return [
            n
            for n in walk(symbol.method)
            if self.is_reference(n) and self.resolve(n) is symbol
        ]

    def captured_or_unresolved(self, symbol):
        for n in walk(symbol.method):
            if (
                n.type != "identifier"
                or self.text(n) != symbol.name
                or not self.is_reference(n)
            ):
                continue
            if contains(symbol.scope, n) and self.resolve(n) is None:
                return True
        return False

    def binding(self, node, expected_type="int"):
        symbol = self.resolve(node)
        return (
            symbol.declaration if symbol and symbol.java_type == expected_type else None
        )

    def references(self, name):
        symbol = self.symbol_for_name(name)
        return self.references_of(symbol) if symbol else []

    def integer(self, node):
        node = unwrap(node)
        if node is None:
            return None
        if node.type == "unary_expression" and self.op(node) in {"-", "+"}:
            child = node.named_children[-1]
            text = self.text(child).replace("_", "")
            suffix = "L" if text[-1:] in {"l", "L"} else ""
            try:
                magnitude = int(text[:-1] if suffix else text)
            except ValueError:
                return None
            limit = 2 ** 63 if suffix else 2 ** 31
            if self.op(node) == "-" and magnitude == limit:
                return -magnitude, suffix
            literal = self.integer(child)
            return (
                ((-literal[0] if self.op(node) == "-" else literal[0]), literal[1])
                if literal
                else None
            )
        return super().integer(node)

    def expression_type(self, node):
        node = unwrap(node)
        if node is None:
            return None
        if node.id in self._types:
            return self._types[node.id]
        result = self._infer_type(node)
        self._types[node.id] = result
        return result

    def _infer_type(self, node):
        literal = self.integer(node)
        if literal is not None:
            return "long" if literal[1] else "int"
        if node.type in {"true", "false"}:
            return "boolean"
        if node.type == "character_literal":
            return "char"
        if node.type == "string_literal":
            return "String"
        if node.type == "identifier":
            symbol = self.resolve(node)
            return symbol.java_type if symbol else None
        if node.type in {"update_expression", "assignment_expression"}:
            left = (
                node.child_by_field_name("left")
                if node.type == "assignment_expression"
                else node.named_children[0]
            )
            symbol = self.resolve(unwrap(left))
            return symbol.java_type if symbol else None
        if node.type == "unary_expression":
            typ = self.expression_type(node.named_children[-1])
            op = self.op(node)
            if op == "!":
                return "boolean" if typ == "boolean" else None
            if op in {"+", "-", "~"} and typ in INTEGRAL:
                return "long" if typ == "long" else "int"
        if node.type == "binary_expression":
            left = self.expression_type(node.child_by_field_name("left"))
            right = self.expression_type(node.child_by_field_name("right"))
            op = self.op(node)
            if left in INTEGRAL and right in INTEGRAL:
                if op in {"<", ">", "<=", ">=", "==", "!="}:
                    return "boolean"
                if op in {"<<", ">>", ">>>"}:
                    return "long" if left == "long" else "int"
                if op in {"+", "-", "*", "/", "%", "&", "|", "^"}:
                    return "long" if "long" in {left, right} else "int"
            if left == right == "boolean" and op in {
                "&&",
                "||",
                "&",
                "|",
                "^",
                "==",
                "!=",
            }:
                return "boolean"
        return None

    def constant_value(self, node, environment=None):
        """Evaluate the supported Java constant subset with int/long wrapping."""
        node = unwrap(node)
        environment = environment or {}
        integer = self.integer(node)
        if integer is not None:
            return integer[0]
        if node.type in {"true", "false"}:
            return node.type == "true"
        if node.type == "identifier":
            symbol = self.resolve(node)
            if symbol and symbol.key in environment:
                return environment[symbol.key]
            if symbol and symbol.final and symbol.java_type in INTEGRAL | {"boolean"} and symbol.initializer is not None:
                # A recursive/self initializer is not a Java constant variable.
                if any(
                    n.type == "identifier" and self.text(n) == symbol.name
                    for n in walk(symbol.initializer)
                ):
                    return None
                return self.constant_value(symbol.initializer, environment)
            return None
        value = None
        if node.type == "unary_expression":
            a = self.constant_value(node.named_children[-1], environment)
            if a is None:
                return None
            op = self.op(node)
            if op == "!" and type(a) is bool:
                return not a
            if type(a) is int and op in {"+", "-", "~"}:
                value = {"+": lambda: a, "-": lambda: -a, "~": lambda: ~a}[op]()
        if node.type == "binary_expression":
            a = self.constant_value(node.child_by_field_name("left"), environment)
            b = self.constant_value(node.child_by_field_name("right"), environment)
            if a is None or b is None:
                return None
            op = self.op(node)
            if op in {"==", "!="}:
                return a == b if op == "==" else a != b
            if (
                type(a) is bool
                and type(b) is bool
                and op in {"&&", "||", "&", "|", "^"}
            ):
                return {
                    "&&": a and b,
                    "||": a or b,
                    "&": a and b,
                    "|": a or b,
                    "^": a != b,
                }[op]
            if type(a) is not int or type(b) is not int:
                return None
            if op in {"<", ">", "<=", ">="}:
                return {"<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]
            operations = {
                "+": lambda: a + b,
                "-": lambda: a - b,
                "*": lambda: a * b,
                "&": lambda: a & b,
                "|": lambda: a | b,
                "^": lambda: a ^ b,
            }
            if op in operations:
                value = operations[op]()
        if value is not None:
            width = 64 if self.expression_type(node) == "long" else 32
            return (value + 2 ** (width - 1)) % (2 ** width) - 2 ** (width - 1)
        return None

    def effects(self, node):
        if node is None:
            return Effects()
        if node.id not in self._effects:
            self._effects[node.id] = self._analyze_effects(unwrap(node))
        return self._effects[node.id]

    def _analyze_effects(self, node):
        typ = node.type
        if self.integer(node) is not None or typ in {
            "true",
            "false",
            "character_literal",
            "string_literal",
            "null_literal",
        }:
            return Effects()
        if typ == "identifier":
            symbol = self.resolve(node)
            return (
                Effects(reads={symbol.key})
                if symbol
                else Effects(reasons={"unresolved_binding"})
            )
        if typ in {"binary_expression", "unary_expression"}:
            result = Effects()
            for child in node.named_children:
                result = result.merge(self.effects(child))
            if self.expression_type(node) is None:
                result.reasons.add("unknown_expression_type")
            if self.op(node) in {"/", "%"}:
                divisor = self.integer(node.child_by_field_name("right"))
                if divisor is None or divisor[0] == 0:
                    result.reasons.add("possible_arithmetic_exception")
            return result
        if typ in {"assignment_expression", "update_expression"}:
            left = (
                node.child_by_field_name("left")
                if typ == "assignment_expression"
                else node.named_children[0]
            )
            symbol = self.resolve(unwrap(left))
            if symbol is None or symbol.java_type not in PRIMITIVES or symbol.final:
                return Effects(reasons={"unsupported_write_target"})
            right = node.child_by_field_name("right")
            if right is not None and self.expression_type(right) not in PRIMITIVES:
                return Effects(reasons={"implicit_boxing_or_unboxing"})
            result = self.effects(right).merge(Effects())
            if typ == "update_expression" or self.op(node) != "=":
                result.reads.add(symbol.key)
            result.writes.add(symbol.key)
            if right is not None and self.expression_type(right) is None:
                result.reasons.add("unknown_expression_type")
            if typ == "assignment_expression" and self.op(node) in {"/=", "%="}:
                divisor = self.integer(right)
                if divisor is None or divisor[0] == 0:
                    result.reasons.add("possible_arithmetic_exception")
            return result
        if typ == "local_variable_declaration":
            result = Effects()
            for decl in [
                n for n in node.named_children if n.type == "variable_declarator"
            ]:
                symbol = self.symbol_for_name(decl.child_by_field_name("name"))
                if symbol is None:
                    result.reasons.add("unresolved_declaration")
                    continue
                result.declarations.add(symbol.key)
                result = result.merge(self.effects(symbol.initializer))
            return result
        if typ in {
            "block",
            "expression_statement",
            "return_statement",
            "empty_statement",
        }:
            result = Effects()
            for child in node.named_children:
                if child.type not in COMMENTS:
                    result = result.merge(self.effects(child))
            return result
        reasons = {
            "method_invocation": "method_call",
            "object_creation_expression": "object_creation",
            "array_creation_expression": "array_creation",
            "array_access": "array_access",
            "field_access": "heap_access",
            "cast_expression": "cast_or_conversion",
            "lambda_expression": "captured_scope",
            "throw_statement": "abrupt_completion",
        }
        return Effects(reasons={reasons.get(typ, "unsupported_expression:" + typ)})

    def pure(self, node, types=INTEGRAL):
        return (
            node is not None
            and self.expression_type(node) in types
            and self.effects(node).pure
        )

    def pure_int(self, node):
        return self.pure(node, {"int"})

    def declaration_symbols(self, statement):
        if statement.type != "local_variable_declaration":
            return []
        return [
            self.symbol_for_name(n.child_by_field_name("name"))
            for n in statement.named_children
            if n.type == "variable_declarator"
        ]

    def assignment_info(self, statement):
        if statement.type != "expression_statement" or not statement.named_children:
            return None
        expr = statement.named_children[0]
        if expr.type != "assignment_expression":
            return None
        left, right = (
            expr.child_by_field_name("left"),
            expr.child_by_field_name("right"),
        )
        symbol = self.resolve(unwrap(left))
        if symbol is None or symbol.final or symbol.java_type not in INTEGRAL:
            return None
        return symbol, right, self.op(expr), expr

    def assignment(self, statement):
        info = self.assignment_info(statement)
        if info and info[2] == "=" and self.pure(info[1]):
            return info[3].child_by_field_name("left"), info[1]
        return None

    def insertion_sites(self, method_entry_only=False):
        for block in self.nodes:
            if block.type != "block" or ancestor(block, "method_declaration") is None:
                continue
            if any(n.type in BARRIERS for n in self._parents_to_method(block)):
                continue
            if method_entry_only and block.parent.type != "method_declaration":
                continue
            yield block, block.start_byte + 1
            for stmt in statements(block):
                if stmt.type in {
                    "return_statement",
                    "throw_statement",
                    "break_statement",
                    "continue_statement",
                }:
                    break
                # The position before the next original statement is reachable
                # whenever the original source compiled; do not insert after a
                # terminal if/switch/try or a loop of unknown completion.
                if stmt.type in {
                    "local_variable_declaration",
                    "expression_statement",
                    "empty_statement",
                }:
                    yield block, stmt.end_byte

    @staticmethod
    def _parents_to_method(node):
        current = node.parent
        while current and current.type != "method_declaration":
            yield current
            current = current.parent
