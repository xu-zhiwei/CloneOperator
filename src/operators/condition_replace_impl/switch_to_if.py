from .base_condition_operator import BaseConditionOperator

class SwitchToIf(BaseConditionOperator):
    def __init__(self, fallthrough_strategy="nesting"):
        """
        :param fallthrough_strategy: 
            - "nesting": Uses nested if-conditions to represent fallthrough (avoids code duplication).
            - "cloning": Copies the fallthrough statements into each branch (more readable, but duplicates code).
        """
        super().__init__()
        self.fallthrough_strategy = fallthrough_strategy

    TERMINATING_BREAK = 'break_statement'

    def _collect_group_statement_nodes(self, group):
        """Collect statement nodes in one switch group (excluding labels/comments)."""
        nodes = []
        for child in group.children:
            if child.type in ['switch_label', 'comment', ':']:
                continue
            nodes.append(child)
        return nodes

    def _collect_group_statements(self, group, source_code):
        """Collect executable statements in a switch group (excluding labels/break)."""
        statements = []
        for child in group.children:
            if child.type in ['switch_label', 'comment', ':']:
                continue
            stmt_text = source_code[child.start_byte:child.end_byte].decode("utf-8").strip()
            if stmt_text == "break;":
                continue
            if stmt_text:
                statements.append(stmt_text)
        return statements

    def _build_condition(self, case_values, switch_var):
        conds = []
        for val in case_values:
            if val.startswith('"') and val.endswith('"'):
                conds.append(f"{val}.equals({switch_var})")
            else:
                conds.append(f"({switch_var} == {val})")
        return " || ".join(conds)

    def _indent_statement(self, stmt, indent):
        """
        Re-indent a statement block to the target indent.
        This prevents nested converted code from accumulating indentation drift.
        """
        lines = stmt.splitlines()
        if not lines:
            return f"{indent}{stmt}"

        # Remove leading/trailing empty lines first.
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        if not lines:
            return ""

        # Find common left padding across non-empty lines.
        min_leading = None
        for line in lines:
            if not line.strip():
                continue
            leading = len(line) - len(line.lstrip(' \t'))
            if min_leading is None or leading < min_leading:
                min_leading = leading
        if min_leading is None:
            min_leading = 0

        normalized = []
        for line in lines:
            if not line.strip():
                normalized.append("")
            else:
                normalized.append(line[min_leading:])

        # For nested generated blocks, first line is often already left-aligned
        # while following lines keep a large inherited base indent.
        if len(normalized) > 1:
            first_leading = len(normalized[0]) - len(normalized[0].lstrip(' \t'))
            if first_leading == 0:
                tail_leadings = []
                for line in normalized[1:]:
                    if line.strip():
                        tail_leadings.append(len(line) - len(line.lstrip(' \t')))
                if tail_leadings:
                    tail_min = min(tail_leadings)
                    if tail_min > 0:
                        compacted = [normalized[0]]
                        for line in normalized[1:]:
                            if line.strip():
                                compacted.append(line[tail_min:])
                            else:
                                compacted.append("")
                        normalized = compacted

        return "\n".join(f"{indent}{line}" if line else "" for line in normalized)

    def _split_case_segments(self, case_groups):
        """
        Split case groups into break-delimited segments.
        Groups in the same segment can fall through to each other.
        """
        segments = []
        current = []
        for group in case_groups:
            current.append(group)
            if group["ends_with_break"]:
                segments.append(current)
                current = []
        if current:
            segments.append(current)
        return segments

    def _parse_group(self, group, source_code):
        labels = self._find_nodes_by_type(group, 'switch_label')

        is_default = any(
            source_code[l.start_byte:l.end_byte].decode("utf-8").startswith("default")
            for l in labels
        )

        case_values = []
        for label in labels:
            label_text = source_code[label.start_byte:label.end_byte].decode("utf-8")
            if label_text.startswith("default"):
                continue
            for child in label.named_children:
                case_values.append(source_code[child.start_byte:child.end_byte].decode("utf-8"))

        stmt_nodes = self._collect_group_statement_nodes(group)
        ends_with_break = bool(stmt_nodes) and stmt_nodes[-1].type == self.TERMINATING_BREAK
        statements = self._collect_group_statements(group, source_code)

        return {
            "is_default": is_default,
            "case_values": case_values,
            "statements": statements,
            "ends_with_break": ends_with_break
        }

    def _normalize_groups(self, groups_data):
        """
        Merge labels-only case groups into the next non-default case group.
        Example: `case 30:` / `case 40: stmt; break;` => one group with 30,40.
        """
        normalized = []
        pending_case_values = []

        for group in groups_data:
            if (
                not group["is_default"]
                and group["case_values"]
                and not group["statements"]
                and not group["ends_with_break"]
            ):
                pending_case_values.extend(group["case_values"])
                continue

            current = {
                "is_default": group["is_default"],
                "case_values": list(group["case_values"]),
                "statements": list(group["statements"]),
                "ends_with_break": group["ends_with_break"]
            }

            if pending_case_values and not current["is_default"]:
                current["case_values"] = pending_case_values + current["case_values"]
                pending_case_values = []

            normalized.append(current)

        return normalized

    def __call__(self, code: str) -> str:
        source_code = code.encode("utf-8")
        
        while True:
            tree = self._parse_code(source_code)
            root_node = tree.root_node

            switch_nodes = self._find_nodes_by_type(root_node, 'switch_expression')
            if not switch_nodes:
                switch_nodes = self._find_nodes_by_type(root_node, 'switch_statement')
            if not switch_nodes:
                break

            replaced = False
            switch_nodes.sort(key=lambda n: n.start_byte, reverse=True)

            for target_node in switch_nodes:
                base_indent, i1, i2 = self._get_indent(source_code, target_node)

                cond_node = target_node.child_by_field_name('condition')
                if cond_node and cond_node.type == 'parenthesized_expression':
                    # Extract inner condition
                    inner = cond_node.named_children[0]
                    switch_var = source_code[inner.start_byte:inner.end_byte].decode("utf-8")
                else:
                    switch_var = source_code[cond_node.start_byte:cond_node.end_byte].decode("utf-8") if cond_node else "unknown"

                body_node = target_node.child_by_field_name('body')
                if not body_node or body_node.type != 'switch_block':
                    continue

                groups = self._find_nodes_by_type(body_node, 'switch_block_statement_group')
                if not groups:
                    continue

                groups_data = [self._parse_group(group, source_code) for group in groups]
                groups_data = self._normalize_groups(groups_data)

                if_code = ""
                case_groups = [g for g in groups_data if not g["is_default"]]
                default_groups = [g for g in groups_data if g["is_default"]]

                # Keep transformation conservative for uncommon multiple-default patterns.
                if len(default_groups) > 1:
                    continue

                default_group = default_groups[0] if default_groups else None

                # Keep conversion simple and safe: only support default at the end.
                if default_group is not None and not groups_data[-1]["is_default"]:
                    continue

                segments = self._split_case_segments(case_groups)
                if not segments and default_group is None:
                    continue

                is_first_segment = True
                for seg in segments:
                    if self.fallthrough_strategy == "cloning":
                        for i, group in enumerate(seg):
                            if not group["case_values"]:
                                continue
                            
                            cond = self._build_condition(group["case_values"], switch_var)
                            
                            accumulated_stmts = []
                            for j in range(i, len(seg)):
                                accumulated_stmts.extend(seg[j]["statements"])
                            
                            if default_group is not None and seg is segments[-1] and not seg[-1]["ends_with_break"]:
                                accumulated_stmts.extend(default_group["statements"])
                                
                            if is_first_segment and i == 0:
                                if_code += f"if ({cond}) {{\n"
                            else:
                                if_code += f" else if ({cond}) {{\n"
                                
                            for stmt in accumulated_stmts:
                                if_code += f"{self._indent_statement(stmt, i1)}\n"
                            
                            if_code += f"{base_indent}}}"
                        
                        is_first_segment = False
                    else:
                        # Nesting strategy
                        seg_case_values = []
                        for g in seg:
                            seg_case_values.extend(g["case_values"])
                        if not seg_case_values:
                            continue

                        seg_cond = self._build_condition(seg_case_values, switch_var)
                        if is_first_segment:
                            if_code += f"if ({seg_cond}) {{\n"
                            is_first_segment = False
                        else:
                            if_code += f" else if ({seg_cond}) {{\n"

                        if len(seg) == 1:
                            for stmt in seg[0]["statements"]:
                                if_code += f"{self._indent_statement(stmt, i1)}\n"
                        else:
                            prefix_case_values = []
                            for group in seg:
                                prefix_case_values.extend(group["case_values"])
                                prefix_cond = self._build_condition(prefix_case_values, switch_var)
                                if_code += f"{i1}if ({prefix_cond}) {{\n"
                                for stmt in group["statements"]:
                                    if_code += f"{self._indent_statement(stmt, i2)}\n"
                                if_code += f"{i1}}}\n"

                        # If the last case in this segment falls through to trailing default,
                        # default statements must run after the segment body as well.
                        if default_group is not None and seg is segments[-1]:
                            if seg and (not seg[-1]["ends_with_break"]):
                                for stmt in default_group["statements"]:
                                    if_code += f"{self._indent_statement(stmt, i1)}\n"

                        if_code += f"{base_indent}}}"

                if default_group is not None:
                    if if_code:
                        if_code += f" else {{\n"
                        for stmt in default_group["statements"]:
                            if_code += f"{self._indent_statement(stmt, i1)}\n"
                        if_code += f"{base_indent}}}"
                    else:
                        if_code = f"{base_indent}{{\n"
                        for stmt in default_group["statements"]:
                            if_code += f"{self._indent_statement(stmt, i1)}\n"
                        if_code += f"{base_indent}}}"

                start_byte = target_node.start_byte
                end_byte = target_node.end_byte
                source_code = source_code[:start_byte] + if_code.encode('utf-8') + source_code[end_byte:]
                replaced = True
                break

            if not replaced:
                break

        return source_code.decode("utf-8")
