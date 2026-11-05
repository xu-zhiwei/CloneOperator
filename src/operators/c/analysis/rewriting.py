"""C11-only premises for directional rewrites of ordinary local int state."""
from operators.tools.source import unwrap, walk
from operators.c.analysis.context import statements


def boolean(ctx, node):
    # C logical operators convert scalar int truth without changing operand order.
    return ctx.pure(node)


def writable(ctx, node):
    return ctx.binding(unwrap(node))


def simple_assignment(ctx, body):
    if body.type == "compound_statement":
        items = statements(body)
        if len(items) != 1:
            return None
        body = items[0]
    info = ctx.assignment(body, require_initialized=False)
    if not info or ctx.op(info[2]) != "=":
        return None
    s, right, _ = info
    if not ctx.pure(right):
        return None
    return s, right


def movable_branch(ctx, node):
    return not any(n.type in {"declaration", "type_definition", "goto_statement", "labeled_statement"}
                   for n in walk(node))
