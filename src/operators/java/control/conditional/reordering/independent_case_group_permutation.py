"""CC1: IndependentCaseGroupPermutation."""
from operators.base.candidate import AnalyzedStrategy, Candidate
from operators.java.analysis.semantic import COMMENTS
from operators.java.control.conditional.tools import CaseGroup, terminates_group
from operators.base.results import Edit
from operators.tools.source import walk


class IndependentCaseGroupPermutation(AnalyzedStrategy):
    strategy_id = "CC1"
    node_types = {"switch_expression"}

    def __init__(self, mode="adjacent", **kwargs):
        super().__init__(**kwargs)
        if mode not in {"adjacent", "all_pairs", "reverse"}:
            raise ValueError("mode must be adjacent, all_pairs or reverse")
        self.mode = mode

    def collect_groups(self, ctx, node):
        block = node.child_by_field_name("body")
        pending = []
        groups = []
        for raw in block.named_children:
            if raw.type in COMMENTS:
                continue
            if raw.type != "switch_block_statement_group":
                ctx.reject(raw, "unsupported_switch_rule")
                return None
            if any("pattern" in n.type or n.type in {"guard", "when"} for n in walk(raw)):
                ctx.reject(raw, "pattern_switch_order_not_supported")
                return None
            pending.append(raw)
            body = [
                n
                for n in raw.named_children
                if n.type != "switch_label" and n.type not in COMMENTS
            ]
            if not body:
                continue
            if not terminates_group(body[-1]):
                ctx.reject(raw, "case_group_fallthrough")
                return None
            if any(
                s.type in {"local_variable_declaration", "class_declaration"}
                for s in body
            ):
                ctx.reject(raw, "case_group_declaration_scope")
                return None
            groups.append(
                CaseGroup(
                    pending[0],
                    raw,
                    [
                        n
                        for p in pending
                        for n in p.named_children
                        if n.type == "switch_label"
                    ],
                    body,
                )
            )
            pending = []
        if pending:
            ctx.reject(pending[0], "trailing_empty_case_group")
            return None
        return groups

    def analyze_site(self, ctx, node):
        groups = self.collect_groups(ctx, node)
        if groups is None or len(groups) < 2:
            return []

        def text(g):
            return ctx.source[g.first.start_byte : g.last.end_byte].decode("utf-8")

        if self.mode == "reverse":
            edits = [
                Edit(g.first.start_byte, g.last.end_byte, text(h))
                for g, h in zip(groups, reversed(groups))
            ]
            return [
                Candidate(node, edits, "reverse_case_groups", {"groups": len(groups)})
            ]
        result = []
        for i, a in enumerate(groups):
            for j in range(i + 1, len(groups)):
                if self.mode == "adjacent" and j != i + 1:
                    continue
                b = groups[j]
                edits = [
                    Edit(a.first.start_byte, a.last.end_byte, text(b)),
                    Edit(b.first.start_byte, b.last.end_byte, text(a)),
                ]
                result.append(
                    Candidate(node, edits, "permute_case_groups", {"indices": [i, j]})
                )
        return result
