"""SS4: ComputationSplitting."""
from operators.base.candidate import AnalyzedStrategy
from operators.tools.source import ancestor, unwrap, walk
from operators.tools.editing import direct_block, splice
from operators.java.statement.ordinary_statement.tools import value_expression


class ComputationSplitting(AnalyzedStrategy):
    strategy_id = "SS4"
    node_types = {
        "expression_statement",
        "return_statement",
        "local_variable_declaration",
    }

    def __init__(self, extract="operands", max_candidates=32, **kwargs):
        super().__init__(**kwargs)
        if extract not in {"operands", "subexpressions"} or max_candidates < 1:
            raise ValueError("Invalid extraction configuration")
        self.extract, self.max_candidates = extract, max_candidates

    def analyze_site(self, ctx, statement):
        if not direct_block(statement):
            return []
        expression = value_expression(statement)
        if expression is None:
            return []
        root = unwrap(expression)
        if root.type != "binary_expression":
            return []
        if not ctx.pure(expression, {"int", "long", "boolean"}):
            return self.reject(
                ctx,
                statement,
                "extraction_expression_has_effect_or_unknown_type",
                effects=sorted(ctx.effects(expression).reasons),
            )
        if statement.type == "expression_statement":
            info = ctx.assignment_info(statement)
            if not info or info[2] != "=" or info[0].java_type not in {"int", "long"}:
                return self.reject(
                    ctx, statement, "extraction_not_plain_local_assignment"
                )
        elif statement.type == "local_variable_declaration":
            symbols = ctx.declaration_symbols(statement)
            if (
                len(symbols) != 1
                or symbols[0] is None
                or symbols[0].final
                or symbols[0].java_type not in {"int", "long", "boolean"}
            ):
                return self.reject(
                    ctx, statement, "extraction_changes_constant_or_narrowing_context"
                )
        elif statement.type == "return_statement":
            method = ancestor(statement, "method_declaration")
            typ = method.child_by_field_name("type")
            if typ is None or ctx.text(typ) not in {"int", "long", "boolean"}:
                return self.reject(
                    ctx, statement, "extraction_changes_return_conversion"
                )
        nodes = (
            list(root.named_children)
            if self.extract == "operands"
            else [
                n
                for n in walk(root)
                if n != root
                and n.type in {"binary_expression", "identifier", "unary_expression"}
            ]
        )
        result = []
        for node in nodes:
            current = node
            protected = False
            while current is not None and current != expression:
                parent = current.parent
                if parent is not None and (
                    parent.type == "ternary_expression"
                    or parent.type == "binary_expression"
                    and ctx.op(parent) in {"&&", "||"}
                    and parent.child_by_field_name("right") == current
                ):
                    protected = True
                    break
                current = parent
            if protected:
                # Even a total primitive read may be definitely assigned only
                # under this guard. Purity alone does not justify extraction.
                ctx.reject(node, "extraction_leaves_short_circuit_guard")
                continue
            typ = ctx.expression_type(node)
            if typ not in {"int", "long"} or ctx.integer(node) is not None:
                continue
            name = ctx.fresh(statement, "sctTemp")
            replacement = splice(ctx, statement, node, name)
            replacement = f"{typ} {name} = {ctx.text(node)};\n" + replacement
            result.append(
                self.accept(
                    ctx,
                    statement,
                    replacement,
                    "extract_" + self.extract,
                    java_type=typ,
                    extracted=ctx.text(node),
                )
            )
            if len(result) >= self.max_candidates:
                break
        return result or self.reject(ctx, statement, "no_extractable_operand")
