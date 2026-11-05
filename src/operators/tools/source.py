"""AST traversal and byte-oriented source editing helpers."""


def walk(node):
    yield node
    for child in node.named_children:
        yield from walk(child)


def ancestor(node, kind):
    while node is not None:
        if node.type == kind:
            return node
        node = node.parent
    return None


def unwrap(node):
    while node is not None and node.type == "parenthesized_expression":
        node = node.named_children[0]
    return node
