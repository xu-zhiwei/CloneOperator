"""Structured normal and abrupt completion, including finally overrides."""
from operators.java.analysis.semantic import statements, COMMENTS


def completion_outcomes(ctx, node, redirected_continues=None):
    """Structured normal/abrupt completion for loop construction.

    Outcomes retain break/continue labels. Finally clauses override pending
    transfers. This is a small structured control-flow analysis, not exception
    inference or an interprocedural CFG. Unknown constructs may complete normally.
    """
    redirected_continues = redirected_continues or {}
    normal = ("normal", None)
    typ = node.type
    if typ in {"return_statement", "throw_statement"}:
        return {(typ, None)}
    if typ in {"break_statement", "continue_statement"}:
        if typ == "continue_statement" and node.id in redirected_continues:
            return {("break_statement", redirected_continues[node.id])}
        label = ctx.text(node.named_children[0]) if node.named_children else None
        return {(typ, label)}
    if typ == "block":
        result = {normal}
        for statement in statements(node):
            if normal not in result:
                break
            result = (result - {normal}) | completion_outcomes(
                ctx, statement, redirected_continues
            )
        return result
    if typ == "if_statement":
        other = node.child_by_field_name("alternative")
        return completion_outcomes(
            ctx, node.child_by_field_name("consequence"), redirected_continues
        ) | (
            completion_outcomes(ctx, other, redirected_continues)
            if other is not None
            else {normal}
        )
    if typ == "labeled_statement":
        label = ctx.text(node.named_children[0])
        result = completion_outcomes(ctx, node.named_children[-1], redirected_continues)
        if ("break_statement", label) in result:
            result = (result - {("break_statement", label)}) | {normal}
        return result
    if typ in {"try_statement", "try_with_resources_statement"}:
        body = node.child_by_field_name("body")
        if body is None:
            return {normal}
        result = completion_outcomes(ctx, body, redirected_continues)
        for clause in node.named_children:
            if clause.type == "catch_clause":
                result |= completion_outcomes(
                    ctx, clause.child_by_field_name("body"), redirected_continues
                )
            elif clause.type == "finally_clause":
                final = completion_outcomes(
                    ctx, clause.named_children[-1], redirected_continues
                )
                result = (result if normal in final else set()) | (final - {normal})
        return result
    if typ == "synchronized_statement":
        body = node.child_by_field_name("body")
        return (
            completion_outcomes(ctx, body, redirected_continues) if body else {normal}
        )
    if typ == "switch_expression":
        body = node.child_by_field_name("body")
        groups = [n for n in body.named_children if n.type not in COMMENTS]
        if any(n.type != "switch_block_statement_group" for n in groups):
            return {normal}
        following = {normal}
        entries = set()
        has_default = False
        for group in reversed(groups):
            sequence = [
                n
                for n in group.named_children
                if n.type != "switch_label" and n.type not in COMMENTS
            ]
            has_default = has_default or any(
                n.type == "switch_label" and ctx.text(n).startswith("default")
                for n in group.named_children
            )
            result = {normal}
            for statement in sequence:
                if normal not in result:
                    break
                result = (result - {normal}) | completion_outcomes(
                    ctx, statement, redirected_continues
                )
            if normal in result:
                result = (result - {normal}) | following
            following = result
            entries |= result
        if not has_default:
            entries.add(normal)
        if ("break_statement", None) in entries:
            entries = (entries - {("break_statement", None)}) | {normal}
        return entries
    if typ in {"while_statement", "do_statement", "for_statement"}:
        body = node.child_by_field_name("body")
        condition = node.child_by_field_name("condition")
        value = ctx.constant_value(condition) if condition is not None else True
        outcomes = completion_outcomes(ctx, body, redirected_continues)
        result = outcomes - {
            normal,
            ("break_statement", None),
            ("continue_statement", None),
        }
        if (
            ("break_statement", None) in outcomes
            or value is not True
            and (
                typ != "do_statement"
                or normal in outcomes
                or ("continue_statement", None) in outcomes
            )
        ):
            result.add(normal)
        return result
    return {normal}
