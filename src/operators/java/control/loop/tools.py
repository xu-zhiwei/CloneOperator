"""Shared analysis and construction helpers for this target."""
from operators.base.candidate import AnalyzedStrategy
from operators.java.analysis.semantic import statements, BARRIERS
from operators.tools.source import ancestor, walk

LOOPS = {"for_statement", "enhanced_for_statement", "while_statement", "do_statement"}


def loop_label(ctx, loop):
    labels = []
    outer = loop
    parent = loop.parent
    while parent and parent.type == "labeled_statement":
        label = parent.named_children[0]
        labels.insert(0, ctx.text(label))
        outer = parent
        parent = parent.parent
    return labels, outer


def continue_target(ctx, node):
    label = ctx.text(node.named_children[0]) if node.named_children else None
    parent = node.parent
    while parent:
        if parent.type in BARRIERS or parent.type == "method_declaration":
            return None
        if label is None and parent.type in LOOPS:
            return parent
        if (
            label is not None
            and parent.type == "labeled_statement"
            and ctx.text(parent.named_children[0]) == label
        ):
            target = parent.named_children[-1]
            while target.type == "labeled_statement":
                target = target.named_children[-1]
            return target if target.type in LOOPS else None
        parent = parent.parent
    return None


def always_abrupt(node):
    if node.type in {
        "return_statement",
        "throw_statement",
        "break_statement",
        "continue_statement",
    }:
        return True
    if node.type == "block":
        body = statements(node)
        return bool(body) and always_abrupt(body[-1])
    if node.type == "if_statement":
        alternative = node.child_by_field_name("alternative")
        return (
            alternative is not None
            and always_abrupt(node.child_by_field_name("consequence"))
            and always_abrupt(alternative)
        )
    return False


class LoopStrategy(AnalyzedStrategy):
    @staticmethod
    def unknown_constant_return_risk(ctx, node, condition):
        method = ancestor(node, "method_declaration")
        typ = method.child_by_field_name("type")
        if typ is None or ctx.text(typ) == "void":
            return False
        references = [n for n in walk(condition) if ctx.is_reference(n)]
        unknown_constant = any(
            ctx.resolve(n) is None
            or (ctx.resolve(n).final and not ctx.resolve(n).parameter)
            for n in references
        )
        if not unknown_constant or any(
            n.type == "method_invocation" for n in walk(condition)
        ):
            return False
        current = node
        while current.parent is not None and current.parent != method:
            parent = current.parent
            if parent.type == "block":
                sequence = statements(parent)
                if current in sequence and any(
                    s.type == "return_statement"
                    for s in sequence[sequence.index(current) + 1 :]
                ):
                    return False
            current = parent
        return True

    def analyze_structure(self, ctx, node):
        body = node.child_by_field_name("body")
        condition = node.child_by_field_name("condition")
        if body is None or condition is None:
            ctx.reject(node, "missing_loop_component")
            return None
        if any(
            n.type
            in {
                "lambda_expression",
                "class_declaration",
                "class_body",
                "record_declaration",
                "switch_rule",
                "yield_statement",
            }
            for n in walk(node)
        ):
            ctx.reject(node, "loop_contains_captured_scope")
            return None
        if any(
            n.type in {"instanceof_expression", "instanceof_pattern", "record_pattern"}
            for n in walk(condition)
        ):
            ctx.reject(node, "loop_condition_pattern_scope")
            return None
        labels, outer = loop_label(ctx, node)
        return body, condition, labels, outer

    @staticmethod
    def first_flag_safe(ctx, node):
        method = ancestor(node, "method_declaration")
        for symbol in ctx.symbols:
            if (
                symbol.method == method
                and not symbol.parameter
                and (symbol.final or symbol.initializer is None)
            ):
                return False
        typ = method.child_by_field_name("type")
        if typ and ctx.text(typ) != "void":
            sequence = statements(method.child_by_field_name("body"))
            if (
                not sequence
                or sequence[-1].type != "return_statement"
                or sequence[-1].start_byte < node.end_byte
            ):
                return False
        return ctx.constant_value(node.child_by_field_name("condition")) is None


def for_components(ctx, node):
    """Java grammar exposes each statement expression as its own field."""
    def sequence(field):
        parts = []
        for child in node.children_by_field_name(field):
            value = ctx.text(child)
            parts.append(value if value.rstrip().endswith(";") else value + ";")
        return "\n".join(parts)
    return sequence("init"), node.child_by_field_name("condition"), sequence("update")


def checked_for_conversion(strategy, ctx, node, do_while=False):
    from operators.java.analysis.completion import completion_outcomes
    if node.parent.type == "labeled_statement":
        return strategy.reject(ctx, node, "labeled_for_conversion_not_supported")
    init, condition, update = for_components(ctx, node)
    body = node.child_by_field_name("body")
    if any(n.type in BARRIERS or n.type in {"instanceof_expression", "record_pattern", "switch_rule", "yield_statement"} for n in walk(node)):
        return strategy.reject(ctx, node, "captured_or_pattern_scope")
    if any(n.type in {"break_statement", "continue_statement"} and n.named_children for n in walk(node)):
        return strategy.reject(ctx, node, "labeled_transfer_not_supported")
    # Exit the body first, so a finally clause executes before the for update.
    label = ctx.fresh(node, "sctBody")
    continues = [n for n in walk(body) if n.type == "continue_statement" and continue_target(ctx, n) == node]
    text = ctx.source[body.start_byte:body.end_byte]
    for cont in sorted(continues, key=lambda n: n.start_byte, reverse=True):
        a, b = cont.start_byte-body.start_byte, cont.end_byte-body.start_byte
        text = text[:a] + f"break {label};".encode() + text[b:]
    outcomes = completion_outcomes(ctx, body, {n.id: label for n in continues})
    reaches_update = ("normal", None) in outcomes or ("break_statement", label) in outcomes
    loop_body = f"{label}: {{\n{text.decode('utf-8')}\n}}\n" + (update if reaches_update else "")
    test = ctx.text(condition) if condition is not None else "true"
    if do_while:
        value = ctx.constant_value(condition) if condition is not None else True
        if value is False:
            return strategy.reject(ctx, node, "compile_time_false_for")
        if value is None and LoopStrategy.unknown_constant_return_risk(ctx, node, condition):
            return strategy.reject(ctx, node, "external_constant_return_reachability_unknown")
        # The do condition must remain reachable under Java's reachability rules.
        if not reaches_update:
            return strategy.reject(ctx, node, "do_condition_unreachable_after_body")
        loop = f"do {{\n{loop_body}\n}} while ({test});"
        if value is not True:
            loop = f"if ({test}) {{\n{loop}\n}}"
    else:
        loop = f"while ({test}) {{\n{loop_body}\n}}"
    return [strategy.accept(ctx, node, "{\n" + init + "\n" + loop + "\n}", "checked_for_do" if do_while else "checked_for_while")]
