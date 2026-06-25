"""O8 - Statement Reordering.

Call ``StatementReorder(...)(code, k=n)`` to reorder independent statements.
``mode`` is ``all`` or ``single``; ``enabled_reorders`` selects the rules and
``max_swaps`` limits the number of changes.
"""

from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

try:
    from .base_operator import BaseOperator
except ImportError:
    from base_operator import BaseOperator


class StatementReorder(BaseOperator):
    """
    Reorders independent local declarations inside a statement block.

    `mode` controls whether all safe swaps or a single swap is applied. The
    optional `enabled_reorders` list can restrict the rules:
    - `adjacent_single_decl_init`: adjacent single declarations with initializers.
    - `adjacent_single_decl_optional_init`: same, but initializer is optional.
    - `adjacent_multi_decl`: adjacent declarations with multiple declarators.
    - `non_adjacent_decl_run`: non-adjacent declarations in one declaration run.
    """

    SUPPORTED_REORDER_TYPES = {
        "adjacent_single_decl_init",
        "adjacent_single_decl_optional_init",
        "adjacent_multi_decl",
        "non_adjacent_decl_run",
    }

    _UNSAFE_NODE_TYPES = {
        "method_invocation",
        "assignment_expression",
        "update_expression",
        "object_creation_expression",
        "array_creation_expression",
        "await_expression",
    }

    @dataclass
    class _DeclInfo:
        declared_names: Set[str]
        read_refs: Set[str]

    def __init__(
        self,
        seed: int = 42,
        max_swaps: int = 20,
        mode: str = "all",
        enabled_reorders: Optional[Set[str] | List[str] | Tuple[str, ...] | str] = None,
    ):
        super().__init__()
        self.seed = seed
        self.max_swaps = max_swaps
        self.mode = mode  # "all" or "single"
        self.enabled_reorders = self._normalize_enabled_reorders(enabled_reorders)
        self.parser = Parser(Language(tsjava.language()))

    def __call__(self, code: str, k: int = 1) -> str:
        modified_code = code
        for _ in range(k):
            source = modified_code.encode("utf-8")
            modified_code = self.transform_statement_reorder(source)
            modified_code = modified_code.decode("utf-8")
        return modified_code

    def transform_statement_reorder(self, source: bytes) -> bytes:
        tree = self.parser.parse(source)
        swaps = self._find_safe_swaps(tree.root_node, source)
        # Sort by the rightmost byte position descending so each applied swap
        # only shifts bytes *before* it, leaving later (lower-address) swaps
        # unaffected.  Also skip any swap whose range overlaps with an already-
        # applied one to avoid cascaded offset corruption.
        swaps_sorted = sorted(swaps, key=lambda s: s[3], reverse=True)
        applied: List[Tuple[int, int]] = []
        for swap in swaps_sorted:
            ls, _le, _rs, re = swap
            if any(max(ls, a_s) < min(re, a_e) for a_s, a_e in applied):
                continue
            source = self._apply_swap(source, swap)
            applied.append((ls, re))
        return source

    def _find_safe_swaps(self, root, source: bytes) -> List[Tuple[int, int, int, int]]:
        swaps: List[Tuple[int, int, int, int]] = []
        limit = 1 if self.mode == "single" else self.max_swaps

        def walk(node):
            if len(swaps) >= limit:
                return
            if node.type == "block":
                pairs = self._collect_swappable_pairs_in_block(node, source, limit - len(swaps))
                swaps.extend(
                    (
                        left_stmt.start_byte,
                        left_stmt.end_byte,
                        right_stmt.start_byte,
                        right_stmt.end_byte,
                    )
                    for left_stmt, right_stmt in pairs
                )
            for child in node.children:
                walk(child)

        walk(root)
        return swaps

    def _collect_swappable_pairs_in_block(self, block_node, source: bytes, remain: int) -> List[Tuple]:
        statements = [child for child in block_node.named_children if self._is_statement_like(child)]
        pairs: List[Tuple] = []

        if remain <= 0:
            return pairs

        allow_no_init = "adjacent_single_decl_optional_init" in self.enabled_reorders
        allow_multi_decl = "adjacent_multi_decl" in self.enabled_reorders

        if (
            "adjacent_single_decl_init" in self.enabled_reorders
            or "adjacent_single_decl_optional_init" in self.enabled_reorders
            or "adjacent_multi_decl" in self.enabled_reorders
        ):
            pairs.extend(
                self._collect_adjacent_pairs(
                    statements,
                    source,
                    remain - len(pairs),
                    allow_no_init=allow_no_init,
                    allow_multi_decl=allow_multi_decl,
                )
            )

        if len(pairs) < remain and "non_adjacent_decl_run" in self.enabled_reorders:
            pairs.extend(
                self._collect_non_adjacent_pairs_in_decl_runs(
                    statements,
                    source,
                    remain - len(pairs),
                    allow_no_init=allow_no_init,
                    allow_multi_decl=allow_multi_decl,
                )
            )

        return pairs

    @staticmethod
    def _is_statement_like(node) -> bool:
        return node.type.endswith("statement") or node.type == "local_variable_declaration"

    def _collect_adjacent_pairs(
        self,
        statements: List,
        source: bytes,
        remain: int,
        allow_no_init: bool,
        allow_multi_decl: bool,
    ) -> List[Tuple]:
        pairs: List[Tuple] = []
        i = 0
        while i < len(statements) - 1 and len(pairs) < remain:
            left_stmt = statements[i]
            right_stmt = statements[i + 1]
            if self._is_safe_decl_stmt_swap(
                left_stmt,
                right_stmt,
                source,
                allow_no_init=allow_no_init,
                allow_multi_decl=allow_multi_decl,
            ):
                pairs.append((left_stmt, right_stmt))
                i += 2
                continue
            i += 1
        return pairs

    def _collect_non_adjacent_pairs_in_decl_runs(
        self,
        statements: List,
        source: bytes,
        remain: int,
        allow_no_init: bool,
        allow_multi_decl: bool,
    ) -> List[Tuple]:
        pairs: List[Tuple] = []
        if remain <= 0:
            return pairs

        i = 0
        while i < len(statements) and len(pairs) < remain:
            if statements[i].type != "local_variable_declaration":
                i += 1
                continue
            start = i
            while i < len(statements) and statements[i].type == "local_variable_declaration":
                i += 1
            end = i
            run = statements[start:end]
            if len(run) < 3:
                continue
            pairs.extend(
                self._pick_non_overlapping_pairs_from_run(
                    run,
                    source,
                    remain - len(pairs),
                    allow_no_init=allow_no_init,
                    allow_multi_decl=allow_multi_decl,
                )
            )
        return pairs

    def _pick_non_overlapping_pairs_from_run(
        self,
        run: List,
        source: bytes,
        remain: int,
        allow_no_init: bool,
        allow_multi_decl: bool,
    ) -> List[Tuple]:
        pairs: List[Tuple] = []
        used_indices: Set[int] = set()
        n = len(run)
        for left_idx in range(n - 1):
            if len(pairs) >= remain:
                break
            if left_idx in used_indices:
                continue
            for right_idx in range(n - 1, left_idx, -1):
                if right_idx in used_indices:
                    continue
                if self._is_safe_decl_stmt_swap(
                    run[left_idx],
                    run[right_idx],
                    source,
                    allow_no_init=allow_no_init,
                    allow_multi_decl=allow_multi_decl,
                ):
                    pairs.append((run[left_idx], run[right_idx]))
                    used_indices.add(left_idx)
                    used_indices.add(right_idx)
                    break
        return pairs

    def _is_safe_decl_stmt_swap(
        self,
        left_stmt,
        right_stmt,
        source: bytes,
        allow_no_init: bool,
        allow_multi_decl: bool,
    ) -> bool:
        if left_stmt.type != "local_variable_declaration" or right_stmt.type != "local_variable_declaration":
            return False

        left_decl = self._extract_decl_stmt_info(
            left_stmt,
            source,
            allow_no_init=allow_no_init,
            allow_multi_decl=allow_multi_decl,
        )
        right_decl = self._extract_decl_stmt_info(
            right_stmt,
            source,
            allow_no_init=allow_no_init,
            allow_multi_decl=allow_multi_decl,
        )
        if not left_decl or not right_decl:
            return False

        # Name collision.
        if left_decl.declared_names & right_decl.declared_names:
            return False

        # Independence: swapping should not alter reads.
        if left_decl.declared_names & right_decl.read_refs:
            return False
        if right_decl.declared_names & left_decl.read_refs:
            return False
        return True

    def _extract_decl_stmt_info(
        self,
        stmt_node,
        source: bytes,
        allow_no_init: bool,
        allow_multi_decl: bool,
    ) -> Optional[_DeclInfo]:
        declarators = [child for child in stmt_node.children if child.type == "variable_declarator"]
        if not declarators:
            return None
        if not allow_multi_decl and len(declarators) != 1:
            return None

        declared_names: Set[str] = set()
        read_refs: Set[str] = set()
        for declarator in declarators:
            name_node = declarator.child_by_field_name("name")
            value_node = declarator.child_by_field_name("value")
            if not name_node:
                return None
            declared_name = source[name_node.start_byte:name_node.end_byte].decode("utf-8")
            declared_names.add(declared_name)

            if value_node is None:
                if not allow_no_init:
                    return None
                continue
            if self._contains_unsafe_node(value_node):
                return None
            read_refs.update(self._collect_identifier_names(value_node, source))
        return self._DeclInfo(declared_names=declared_names, read_refs=read_refs)

    def _normalize_enabled_reorders(
        self, enabled_reorders: Optional[Set[str] | List[str] | Tuple[str, ...] | str]
    ) -> Set[str]:
        if enabled_reorders is None:
            return self.SUPPORTED_REORDER_TYPES.copy()
        
        if isinstance(enabled_reorders, str):
            parts = [p.strip() for p in enabled_reorders.split(",") if p.strip()]
            parsed = set(parts)
        else:
            parsed = set(enabled_reorders)

        intersection = parsed & self.SUPPORTED_REORDER_TYPES
        
        if not parsed or not intersection:
            return self.SUPPORTED_REORDER_TYPES.copy()

        unknown = parsed - intersection
        print(f"Warning: Ignoring unknown reorder rules: {unknown}")
        return intersection
        

    def _contains_unsafe_node(self, node) -> bool:
        if node.type in self._UNSAFE_NODE_TYPES:
            return True

        for child in node.children:
            if self._contains_unsafe_node(child):
                return True
        return False

    def _collect_identifier_names(self, node, source: bytes) -> Set[str]:
        names: Set[str] = set()

        def walk(curr):
            if curr.type == "identifier":
                names.add(source[curr.start_byte:curr.end_byte].decode("utf-8"))
            for child in curr.children:
                walk(child)

        walk(node)
        return names

    @staticmethod
    def _apply_swap(source: bytes, swap: Tuple[int, int, int, int]) -> bytes:
        left_start, left_end, right_start, right_end = swap
        left_code = source[left_start:left_end]
        right_code = source[right_start:right_end]
        middle = source[left_end:right_start]

        return source[:left_start] + right_code + middle + left_code + source[right_end:]
