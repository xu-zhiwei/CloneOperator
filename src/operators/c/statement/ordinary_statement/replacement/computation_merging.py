"""C11 SS5: ComputationMerging."""
from operators.c.tools.strategy import CStrategy
from operators.base.candidate import Candidate


class ComputationMerging(CStrategy):
    strategy_id = "SS5"
    node_types = {"compound_statement"}

    def analyze_site(self, ctx, node):
        if not self.function_safe(ctx, node):
            return self.reject(ctx, node, "complex_scope_or_control")
        out = []
        for a, b in self.adjacent(ctx, node):
            s, info = ctx.declaration(a), ctx.assignment(b)
            if (
                not s
                or not s.initializer
                or not ctx.pure(s.initializer)
                or not info
                or ctx.op(info[2]) != "="
                or info[0] is s
            ):
                continue
            refs = ctx.references_of(s)
            if len(refs) != 1 or not (
                info[1].start_byte <= refs[0].start_byte < info[1].end_byte
            ):
                continue
            # Inlining into short-circuit or conditional evaluation would move evaluation.
            current = refs[0].parent
            unsafe = False
            while current and current != b:
                if (
                    current.type == "conditional_expression"
                    or current.type == "binary_expression"
                    and ctx.op(current) in {"&&", "||"}
                ):
                    unsafe = True
                current = current.parent
            if unsafe:
                continue
            expr = ctx.source[b.start_byte : b.end_byte]
            ref = refs[0]
            start, end = ref.start_byte - b.start_byte, ref.end_byte - b.start_byte
            merged = (
                expr[:start]
                + ("(" + ctx.text(s.initializer) + ")").encode()
                + expr[end:]
            ).decode()
            out.append(
                Candidate(
                    a,
                    [ctx.edit(a, ""), ctx.edit(b, merged)],
                    "single_use_computation_merging",
                )
            )
        return out
