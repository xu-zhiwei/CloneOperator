"""Shared analysis and construction helpers for this target."""


def computational(ctx, statement):
    if statement.type != "expression_statement" or not statement.named_children:
        return False
    expression = statement.named_children[0]
    return (
        expression.type in {"assignment_expression", "update_expression"}
        and not ctx.effects(expression).reasons
    )


def value_expression(statement):
    if statement.type == "return_statement" and statement.named_children:
        return statement.named_children[0]
    if statement.type == "expression_statement" and statement.named_children:
        expr = statement.named_children[0]
        if expr.type == "assignment_expression":
            return expr.child_by_field_name("right")
    if statement.type == "local_variable_declaration":
        decls = [n for n in statement.named_children if n.type == "variable_declarator"]
        if len(decls) == 1:
            return decls[0].child_by_field_name("value")
    return None
