"""Shared analysis and construction helpers for this target."""
from dataclasses import dataclass
from operators.base.candidate import AnalyzedStrategy
from operators.java.analysis.semantic import statements
from operators.tools.source import unwrap, walk


def constant_boolean(ctx, node):
    node = unwrap(node)
    if node.type in {"true", "false"}:
        return node.type == "true"
    if node.type == "unary_expression" and ctx.op(node) == "!":
        value = constant_boolean(ctx, node.named_children[-1])
        return None if value is None else not value
    if node.type == "binary_expression" and ctx.op(node) in {
        "&&",
        "||",
        "&",
        "|",
        "^",
        "==",
        "!=",
    }:
        a = constant_boolean(ctx, node.child_by_field_name("left"))
        b = constant_boolean(ctx, node.child_by_field_name("right"))
        if a is not None and b is not None:
            return {
                "&&": a and b,
                "||": a or b,
                "&": a and b,
                "|": a or b,
                "^": a != b,
                "==": a == b,
                "!=": a != b,
            }[ctx.op(node)]
    return None


def checked_exception_risk(node):
    return any(
        n.type
        in {
            "method_invocation",
            "object_creation_expression",
            "throw_statement",
            "try_statement",
            "try_with_resources_statement",
            "class_declaration",
            "lambda_expression",
        }
        for n in walk(node)
    )


def terminates_group(statement):
    if statement.type in {"return_statement", "throw_statement"}:
        return True
    if statement.type == "break_statement":
        return not statement.named_children
    if statement.type == "block":
        body = statements(statement)
        return bool(body) and terminates_group(body[-1])
    if statement.type == "if_statement":
        a, b = (
            statement.child_by_field_name("consequence"),
            statement.child_by_field_name("alternative"),
        )
        return b is not None and terminates_group(a) and terminates_group(b)
    return False


@dataclass
class CaseGroup:
    first: object
    last: object
    labels: list
    body: list


class ConditionalStrategy(AnalyzedStrategy):
    node_types = {"if_statement"}

    @staticmethod
    def ordinary_condition(ctx, node):
        condition = node.child_by_field_name("condition")
        # Pattern bindings need Java-version-dependent flow scoping. Keep their
        # cases explicit rather than confusing them with ordinary boolean tests.
        if any(
            n.type in {"instanceof_expression", "instanceof_pattern", "record_pattern"}
            for n in walk(condition)
        ):
            ctx.reject(condition, "pattern_condition_scope_not_supported")
            return None
        return unwrap(condition)


def checked_if_chain(ctx, node, min_case_count=1):
    """Stable primitive selector, distinct typed constants and intact bodies."""
    from operators.tools.source import ancestor
    method = ancestor(node, "method_declaration")
    # A constant-true if can establish definite assignment without an else.
    # A switch on that same constant still needs a default for javac's flow
    # analysis. Do not claim equivalence of those static flow facts.
    if any(s.method == method and not s.parameter and s.initializer is None for s in ctx.symbols):
        return None
    selector = None
    seen = set()
    branches = []
    current = node
    while current is not None and current.type == "if_statement":
        pending = [unwrap(current.child_by_field_name("condition"))]
        values = []
        while pending:
            term = unwrap(pending.pop())
            if term.type == "binary_expression" and ctx.op(term) == "||":
                pending.extend([term.child_by_field_name("right"), term.child_by_field_name("left")])
                continue
            if term.type != "binary_expression" or ctx.op(term) != "==":
                return None
            left, right = term.child_by_field_name("left"), term.child_by_field_name("right")
            symbol = ctx.resolve(unwrap(left))
            value = ctx.integer(right)
            if (symbol is None or symbol.java_type not in {"int", "short", "byte", "char"}
                    or value is None or value[1] or value[0] in seen):
                return None
            limits = {"byte": (-128, 127), "short": (-32768, 32767), "char": (0, 65535),
                      "int": (-2**31, 2**31-1)}
            lo, hi = limits[symbol.java_type]
            if not lo <= value[0] <= hi or selector is not None and selector is not symbol:
                return None
            selector = symbol
            seen.add(value[0])
            values.append(value[0])
        body = current.child_by_field_name("consequence")
        branches.append((values, body))
        current = current.child_by_field_name("alternative")
    if len(seen) < min_case_count:
        return None
    # Breaks can acquire a new switch target. Captured scopes and pattern
    # bindings require a richer compiler analysis and remain unsupported.
    for body in [b for _, b in branches] + ([current] if current else []):
        if any(n.type in {"break_statement", "class_declaration", "class_body", "lambda_expression",
                          "instanceof_expression", "record_pattern", "switch_rule", "yield_statement"} for n in walk(body)):
            return None
    return selector, branches, current


def checked_switch_groups(ctx, node):
    """Traditional statement switch with no declarations or internal transfers."""
    from operators.tools.source import ancestor
    parent = node.parent
    if parent.type not in {"block", "if_statement", "while_statement", "for_statement",
                           "do_statement", "labeled_statement", "switch_block_statement_group"}:
        return None
    if parent.type == "labeled_statement":
        return None
    condition = node.child_by_field_name("condition")
    if not ctx.pure(condition, {"int", "short", "byte", "char"}):
        return None
    # Independent if guards do not communicate definite assignment to javac.
    # Keep all variants within the same verified assignment fragment.
    method = ancestor(node, "method_declaration")
    return_type = method.child_by_field_name("type")
    tail = statements(method.child_by_field_name("body"))
    if (return_type is not None and ctx.text(return_type) != "void"
            and not (tail and tail[-1].type == "return_statement" and tail[-1].start_byte >= node.end_byte)):
        return None
    if any(s.method == method and not s.parameter and (s.final or s.initializer is None)
           for s in ctx.symbols):
        return None
    result, labels = [], []
    seen = set()
    default_seen = False
    body = node.child_by_field_name("body")
    for raw in statements(body):
        if raw.type != "switch_block_statement_group":
            return None
        content = []
        for child in statements(raw):
            if child.type == "switch_label":
                if ctx.text(child).strip() == "default":
                    if default_seen:
                        return None
                    default_seen = True
                    labels.append(None)
                else:
                    constants = [n for n in child.named_children if n.type not in {"line_comment", "block_comment"}]
                    if len(constants) != 1:
                        return None
                    value = ctx.integer(constants[0])
                    if value is None or value[1] or value[0] in seen:
                        return None
                    seen.add(value[0])
                    labels.append(value[0])
            else:
                content.append(child)
        if not content:
            continue
        for statement in content:
            for n in walk(statement):
                if n.type in {"local_variable_declaration", "class_declaration", "class_body",
                              "lambda_expression", "switch_expression", "continue_statement",
                              "labeled_statement", "try_statement", "try_with_resources_statement"}:
                    return None
                if n.type == "break_statement" and (n != content[-1] or n.named_children):
                    return None
        terminal = content[-1].type if content[-1].type in {"break_statement", "return_statement", "throw_statement"} else None
        if terminal is None:
            from operators.java.analysis.completion import completion_outcomes
            if ("normal", None) not in completion_outcomes(ctx, content[-1]):
                terminal = "abrupt"
        code = "\n".join(ctx.text(s) for s in content if s.type != "break_statement")
        result.append((labels, code, terminal))
        labels = []
    if labels:
        result.append((labels, "", False))
    return (condition, result) if result else None


def construct_if_switch(strategy, ctx, node, cloning=False):
    from operators.java.analysis.completion import completion_outcomes
    checked = checked_if_chain(ctx, node, strategy.min_case_count)
    if checked is None:
        return strategy.reject(ctx, node, "if_switch_binding_type_or_control_unknown")
    selector, branches, default = checked
    parts = []
    for values, body in branches:
        ending = "break;" if ("normal", None) in completion_outcomes(ctx, body) else ""
        if cloning:
            parts.extend(f"case {v}: {{\n{ctx.text(body)}\n{ending}\n}}" for v in values)
        else:
            parts.append("\n".join(f"case {v}:" for v in values) + f"\n{{\n{ctx.text(body)}\n{ending}\n}}")
    if default is not None:
        parts.append("default: {\n" + ctx.text(default) + "\n}")
    return [strategy.accept(ctx, node, "switch (" + selector.name + ") {\n" + "\n".join(parts) + "\n}",
                            "checked_if_switch_cloning" if cloning else "checked_if_switch_nesting")]


def construct_switch_if(strategy, ctx, node, cloning=False):
    checked = checked_switch_groups(ctx, node)
    if checked is None:
        return strategy.reject(ctx, node, "switch_scope_control_or_assignment_unknown")
    condition, groups = checked
    name = ctx.fresh(node, "sctSelector")
    values = [v for labels, _, _ in groups for v in labels if v is not None]
    def guard(labels):
        terms = [f"{name} == {v}" for v in labels if v is not None]
        if None in labels:
            terms.append("(" + " && ".join(f"{name} != {v}" for v in values) + ")" if values else "true")
        return " || ".join(terms)
    parts = []
    if cloning:
        for i, (labels, _, _) in enumerate(groups):
            tail = []
            for _, code, terminal in groups[i:]:
                tail.append(code)
                if terminal:
                    break
            parts.append(("if" if i == 0 else "else if") + " (" + guard(labels) + ") {\n" + "\n".join(tail) + "\n}")
    else:
        active = ctx.fresh(node, "sctActive")
        parts.append(f"boolean {active} = false;")
        for labels, code, terminal in groups:
            # Only a direct switch break needs deactivation. A return or
            # throw has no successor and must not gain unreachable statements.
            ending = f"{active} = false;" if terminal == "break_statement" else ""
            parts.append(f"if ({guard(labels)}) {active} = true;")
            parts.append(f"if ({active}) {{\n{code}\n{ending}\n}}")
    return [strategy.accept(ctx, node, f"{{\nint {name} = {ctx.text(condition)};\n" + "\n".join(parts) + "\n}",
                            "checked_switch_if_cloning" if cloning else "checked_switch_if_nesting")]
