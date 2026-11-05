"""Conservative premises for reversible expression and branch rewrites."""
from operators.tools.source import unwrap, walk
from operators.java.analysis.semantic import statements


def boolean(ctx, node):
    return ctx.pure(node, {"boolean"})


def writable(ctx, node):
    node = unwrap(node)
    if node is None or node.type != "identifier":
        return None
    s = ctx.resolve(node)
    return s if s and not s.final and s.java_type in {"int", "long"} else None


def simple_assignment(ctx, body):
    if body.type == "block":
        items = statements(body)
        if len(items) != 1:
            return None
        body = items[0]
    if body.type != "expression_statement" or len(body.named_children) != 1:
        return None
    expr = body.named_children[0]
    if expr.type != "assignment_expression" or ctx.op(expr) != "=":
        return None
    left, right = expr.child_by_field_name("left"), expr.child_by_field_name("right")
    s = writable(ctx, left)
    if not s or ctx.expression_type(right) != s.java_type or not ctx.pure(right, {s.java_type}):
        return None
    return s, right


def movable_branch(ctx, node):
    # No declarations or flow-scoped names may acquire a new lexical environment.
    excluded = {"local_variable_declaration", "class_declaration", "enum_declaration", "record_declaration",
                "interface_declaration", "annotation_type_declaration", "class_body", "lambda_expression",
                "instanceof_expression", "record_pattern", "labeled_statement", "switch_rule", "yield_statement"}
    return not any(n.type in excluded for n in walk(node))
