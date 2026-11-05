"""C switch groups and loop-target-aware construction helpers."""
from dataclasses import dataclass
from operators.tools.source import walk, ancestor, unwrap
from operators.c.analysis.context import statements, LOOPS


@dataclass
class CaseGroup:
    labels: list
    nodes: list
    value_nodes: list

    def body(self, ctx, strip_break=False):
        nodes = (
            self.nodes[:-1]
            if strip_break and self.nodes and self.nodes[-1].type == "break_statement"
            else self.nodes
        )
        return "\n".join(ctx.text(n) for n in nodes)

    @property
    def terminal(self):
        return bool(self.nodes) and self.nodes[-1].type in {
            "break_statement",
            "return_statement",
        }


def groups(ctx, node):
    body = node.child_by_field_name("body")
    items = statements(body)
    if not items or any(n.type != "case_statement" for n in items):
        return None
    result, labels, values = [], [], []
    seen = set()
    default = False
    for item in items:
        value = item.child_by_field_name("value")
        number = ctx.integer(value) if value else None
        if value and (number is None or number in seen) or not value and default:
            return None
        if value:
            seen.add(number)
        else:
            default = True
        labels.append(number)
        values.append(value)
        body_nodes = [
            n for n in item.named_children if n != value and n.type != "comment"
        ]
        if body_nodes:
            result.append(CaseGroup(labels, body_nodes, values))
            labels, values = [], []
    if labels:
        result.append(CaseGroup(labels, [], values))
    return result


def switch_safe(ctx, node, allow_fallthrough=False):
    selector = unwrap(node.child_by_field_name("condition"))
    if not ctx.binding(selector) or not ctx.pure(selector):
        return None
    gs = groups(ctx, node)
    if not gs:
        return None
    for g in gs:
        for st in g.nodes:
            if any(
                n.type
                in {
                    "declaration",
                    "goto_statement",
                    "labeled_statement",
                    "continue_statement",
                    "case_statement",
                    "switch_statement",
                }
                for n in walk(st)
            ):
                return None
            # Only the group's final direct break can target this switch.
            if any(n.type == "break_statement" and n != g.nodes[-1] for n in walk(st)):
                return None
        if not allow_fallthrough and not g.terminal:
            return None
    return selector, gs


def equality_chain(ctx, condition):
    condition = unwrap(condition)
    if condition.type == "binary_expression" and ctx.op(condition) == "||":
        a = equality_chain(ctx, condition.child_by_field_name("left"))
        b = equality_chain(ctx, condition.child_by_field_name("right"))
        return a + b if a and b else None
    if condition.type != "binary_expression" or ctx.op(condition) != "==":
        return None
    l, r = condition.child_by_field_name("left"), condition.child_by_field_name("right")
    for name, value in ((l, r), (r, l)):
        s, v = ctx.binding(name), ctx.integer(value)
        if s and v is not None and ctx.pure(name):
            return [(s, v)]
    return None


def if_chain(ctx, node):
    if (
        node.parent.type == "if_statement"
        and node.parent.child_by_field_name("alternative") == node
    ):
        return None
    branches, selector, seen = [], None, set()
    branch = node
    while branch is not None and branch.type == "if_statement":
        pairs = equality_chain(ctx, branch.child_by_field_name("condition"))
        if not pairs:
            return None
        values = []
        for symbol, value in pairs:
            if selector is None:
                selector = symbol
            if selector is not symbol or value in seen:
                return None
            values.append(value)
            seen.add(value)
        body = branch.child_by_field_name("consequence")
        # A new switch must not capture an existing loop break.
        if any(
            n.type in {"break_statement", "goto_statement", "labeled_statement"}
            for n in walk(body)
        ):
            return None
        branches.append((values, ctx.text(body)))
        branch = ctx.alternative(branch)
    if branch and any(
        n.type in {"break_statement", "goto_statement", "labeled_statement"}
        for n in walk(branch)
    ):
        return None
    return selector, branches, ctx.text(branch) if branch else None


def target_loop(node):
    p = node.parent
    while p and p.type not in LOOPS:
        p = p.parent
    return p


def for_parts(ctx, node):
    init = node.child_by_field_name("initializer")
    cond = node.child_by_field_name("condition")
    update = node.child_by_field_name("update")
    return (
        ctx.text(init).rstrip(";") + ";" if init else "",
        ctx.text(cond) if cond else "1",
        ctx.text(update),
    )


def loop_body(ctx, node, update=""):
    """Insert for-update before only continues targeting this loop.

    Reject possible capture of names in the copied update by body declarations.
    Keeping the original body as a nested block preserves its declaration scope.
    """
    body = node.child_by_field_name("body")
    if not update:
        return ctx.text(body)
    update_node = node.child_by_field_name("update")
    names = {ctx.text(n) for n in walk(update_node) if n.type == "identifier"}
    local_names = {
        s.name
        for s in ctx.symbols
        if body.start_byte <= s.node.start_byte < body.end_byte
    }
    if names & local_names:
        return None
    source = ctx.source[body.start_byte : body.end_byte]
    edits = []
    for n in walk(body):
        if n.type == "continue_statement" and target_loop(n) == node:
            edits.append(
                (
                    n.start_byte - body.start_byte,
                    n.end_byte - body.start_byte,
                    "{ " + update + "; continue; }",
                )
            )
    for start, end, replacement in reversed(edits):
        source = source[:start] + replacement.encode() + source[end:]
    return source.decode("utf-8")
