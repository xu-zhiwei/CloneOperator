"""Edits inside parsed ranges and block checks."""


def splice(ctx, outer, inner, replacement):
    source = ctx.source[outer.start_byte : outer.end_byte]
    start, end = inner.start_byte - outer.start_byte, inner.end_byte - outer.start_byte
    return (source[:start] + replacement.encode("utf-8") + source[end:]).decode("utf-8")


def direct_block(node):
    return node.parent is not None and node.parent.type == "block"


def apply_disjoint_edits(source, candidates, limit, parser):
    """Apply checked candidates in disjoint original source regions.

    Batch compatibility operations may modify multiple sites in one round.
    Reject overlapping regions rather than reselecting a just-swapped site.
    """
    selected = []
    regions = []
    for candidate in candidates:
        start = min(edit.start_byte for edit in candidate.edits)
        end = max(edit.end_byte for edit in candidate.edits)
        if any(max(start, a) < min(end, b) for a, b in regions):
            continue
        selected.extend(candidate.edits)
        regions.append((start, end))
        if len(regions) >= limit:
            break
    data = source
    for edit in sorted(selected, key=lambda item: item.start_byte, reverse=True):
        data = (
            data[: edit.start_byte]
            + edit.replacement.encode("utf-8")
            + data[edit.end_byte :]
        )
    return (
        source.decode("utf-8")
        if parser.parse(data).root_node.has_error
        else data.decode("utf-8")
    )
