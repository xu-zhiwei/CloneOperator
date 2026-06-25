import re

from .base_condition_operator import BaseConditionOperator

class IfToSwitch(BaseConditionOperator):
    BREAKABLE_ANCESTORS = {
        "switch_statement",
        "switch_expression",
        "for_statement",
        "enhanced_for_statement",
        "while_statement",
        "do_statement",
    }

    FLOAT_LITERAL_TYPES = {
        "decimal_floating_point_literal",
        "hex_floating_point_literal",
    }
    CASE_VALUE_SYMBOL_TYPES = {
        "identifier",
        "scoped_identifier",
        "field_access",
    }

    def __init__(self, multi_case_strategy="nesting", min_case_count=1):
        """
        :param multi_case_strategy:
            - "nesting": Generate fallthrough-style switch labels for OR-equality chains.
              Example: case 2: case 3: <body> break;
            - "cloning": Clone the same body for each case value.
              Example: case 2: <body> break; case 3: <body> break;
        :param min_case_count:
            - Minimum number of parsed case values needed before conversion.
              Use 1 to also allow single-branch `if (x == literal)`.
        """
        super().__init__()
        self.multi_case_strategy = multi_case_strategy
        self.min_case_count = min_case_count

    def _is_break_guarded_by_inner_breakable(self, break_node, boundary_if):
        current = break_node.parent
        while current and current != boundary_if:
            if current.type in self.BREAKABLE_ANCESTORS:
                return True
            current = current.parent
        return False

    def has_unsafe_unlabelled_break(self, node, boundary_if):
        """Detect unlabelled `break;` that would change target after conversion."""
        if node.type == 'break_statement':
            has_label = any(child.type == 'identifier' for child in node.named_children)
            if not has_label and not self._is_break_guarded_by_inner_breakable(node, boundary_if):
                return True
        for child in node.children:
            if self.has_unsafe_unlabelled_break(child, boundary_if):
                return True
        return False

    def is_root_if(self, node):
        """Determine if this if_statement is the start of an else-if chain"""
        parent = node.parent
        if parent and parent.type == 'if_statement':
            if parent.child_by_field_name('alternative') == node:
                return False
        return True

    def _get_binary_operator(self, binary_node, source_code):
        operator_node = binary_node.child_by_field_name('operator')
        if operator_node:
            return source_code[
                operator_node.start_byte:operator_node.end_byte
            ].decode()
        if len(binary_node.children) >= 3:
            return source_code[
                binary_node.children[1].start_byte:
                binary_node.children[1].end_byte
            ].decode()
        return None

    def _strip_parens(self, node):
        current = node
        while (
            current
            and current.type == 'parenthesized_expression'
            and len(current.named_children) == 1
        ):
            current = current.named_children[0]
        return current

    def _is_literal(self, ast_node):
        return ast_node is not None and 'literal' in ast_node.type

    def _looks_like_constant_symbol(self, value_code):
        """
        Heuristic gate for symbolic case labels.
        Accept names like CONST, Type.CONST, pkg.Type.CONST, Enum.VALUE.
        """
        tail = value_code.split('.')[-1].strip()
        return bool(re.fullmatch(r"[A-Z_][A-Z0-9_]*", tail))

    def _extract_unary_case_value(self, node, source_code):
        if not node or node.type != "unary_expression":
            return None
        if len(node.named_children) != 1:
            return None

        operand = node.named_children[0]
        if not self._is_literal(operand):
            return None

        operator = None
        for child in node.children:
            token = source_code[child.start_byte:child.end_byte].decode().strip()
            if token in ("+", "-"):
                operator = token
                break
        if operator is None:
            return None

        operand_code = self._node_code(operand, source_code)
        return f"{operator}{operand_code}", operand.type

    def _extract_case_value(self, node, source_code):
        current = self._strip_parens(node)
        if not current:
            return None

        if self._is_literal(current):
            return self._node_code(current, source_code), current.type

        unary_value = self._extract_unary_case_value(current, source_code)
        if unary_value is not None:
            return unary_value

        if current.type in self.CASE_VALUE_SYMBOL_TYPES:
            value_code = self._node_code(current, source_code)
            if self._looks_like_constant_symbol(value_code):
                return value_code, current.type

        return None

    def _node_code(self, node, source_code):
        if not node:
            return ""
        return source_code[node.start_byte:node.end_byte].decode().strip()

    def _extract_equals_invocation_pair(self, node, source_code):
        if not node or node.type != "method_invocation":
            return None

        method_name = self._node_code(node.child_by_field_name("name"), source_code)
        if method_name != "equals":
            return None

        obj_node = node.child_by_field_name("object")
        args_node = node.child_by_field_name("arguments")
        if not obj_node or not args_node:
            return None
        if len(args_node.named_children) != 1:
            return None

        arg_node = args_node.named_children[0]
        valid_var_types = ['identifier', 'field_access']

        arg_case_value = self._extract_case_value(arg_node, source_code)
        obj_case_value = self._extract_case_value(obj_node, source_code)

        if obj_node.type in valid_var_types and arg_case_value is not None:
            return [(
                self._node_code(obj_node, source_code),
                arg_case_value[0],
                arg_case_value[1]
            )]

        if arg_node.type in valid_var_types and obj_case_value is not None:
            return [(
                self._node_code(arg_node, source_code),
                obj_case_value[0],
                obj_case_value[1]
            )]

        return None

    def _extract_case_pairs(self, expr_node, source_code):
        """
        Parse condition expression into (var_name, value_literal) pairs.
        Supports:
          - x == 1
          - x == 2 || x == 3
          - s.equals("A"), "A".equals(s)
        """
        node = self._strip_parens(expr_node)
        if not node:
            return None

        if node.type == "method_invocation":
            return self._extract_equals_invocation_pair(node, source_code)

        if node.type != 'binary_expression':
            return None

        op = self._get_binary_operator(node, source_code)

        # Support OR-chain of equality checks and flatten it recursively.
        if op == '||':
            left = node.child_by_field_name('left')
            right = node.child_by_field_name('right')
            if not left or not right:
                return None

            left_pairs = self._extract_case_pairs(left, source_code)
            right_pairs = self._extract_case_pairs(right, source_code)
            if left_pairs is None or right_pairs is None:
                return None
            return left_pairs + right_pairs

        # Base case: a single equality check.
        if op != '==':
            return None

        left = node.child_by_field_name('left')
        right = node.child_by_field_name('right')
        if not left or not right:
            return None

        valid_var_types = ['identifier', 'field_access']
        right_case_value = self._extract_case_value(right, source_code)
        left_case_value = self._extract_case_value(left, source_code)

        if left.type in valid_var_types and right_case_value is not None:
            var_name = source_code[left.start_byte:left.end_byte].decode()
            return [(var_name, right_case_value[0], right_case_value[1])]

        if right.type in valid_var_types and left_case_value is not None:
            var_name = source_code[right.start_byte:right.end_byte].decode()
            return [(var_name, left_case_value[0], left_case_value[1])]

        return None

    def parse_if_chain(self, if_node, source_code):
        target_identifier = None
        case_groups = []
        default_body = None
        seen_cases = set()

        current_node = if_node

        while current_node and current_node.type == 'if_statement':
            if self.has_unsafe_unlabelled_break(current_node, current_node):
                return None

            cond_node = current_node.child_by_field_name('condition')
            if not cond_node:
                return None

            case_pairs = self._extract_case_pairs(cond_node, source_code)
            if not case_pairs:
                return None

            for var_name, val_code, val_type in case_pairs:
                # ========= Filters =========
                # 1. No boolean
                if val_code in ['true', 'false']:
                    return None
                # 2. No float literals
                if val_type in self.FLOAT_LITERAL_TYPES:
                    return None
                # 3. Deduplicate cases
                if val_code in seen_cases:
                    return None

                seen_cases.add(val_code)

                # Target variable must be consistent
                if target_identifier is None:
                    target_identifier = var_name
                elif target_identifier != var_name:
                    return None

            cons_node = current_node.child_by_field_name('consequence')

            if not cons_node:
                return None

            cons_code = source_code[
                cons_node.start_byte:cons_node.end_byte
            ].decode().strip()

            if cons_code.startswith('{') and cons_code.endswith('}'):
                cons_code = cons_code[1:-1].strip()

            group_values = [val_code for _, val_code, _ in case_pairs]
            case_groups.append((group_values, cons_code))

            alt_node = current_node.child_by_field_name('alternative')

            if alt_node:
                if alt_node.type == 'if_statement':
                    current_node = alt_node
                else:
                    alt_code = source_code[
                        alt_node.start_byte:alt_node.end_byte
                    ].decode().strip()

                    if alt_code.startswith('{') and alt_code.endswith('}'):
                        alt_code = alt_code[1:-1].strip()

                    default_body = alt_code
                    break
            else:
                break

        # Require enough parsed case labels before conversion.
        total_case_count = sum(len(vals) for vals, _ in case_groups)
        if total_case_count < self.min_case_count:
            return None

        return target_identifier, case_groups, default_body

    def __call__(self, code: str) -> str:
        source_code = code.encode("utf-8")
        
        while True:
            tree = self._parse_code(source_code)
            root_node = tree.root_node

            all_ifs = self._find_nodes_by_type(root_node, 'if_statement')
            root_ifs = [n for n in all_ifs if self.is_root_if(n)]
            
            replaced = False
            
            for if_node in reversed(root_ifs):
                result = self.parse_if_chain(if_node, source_code)
                if result is not None:
                    target_var, case_groups, default_body = result
                    
                    base_indent, i1, i2 = self._get_indent(source_code, if_node)
                    
                    switch_code = f"switch ({target_var}) {{\n"
                    
                    for vals, body in case_groups:
                        if self.multi_case_strategy == "cloning":
                            for val in vals:
                                switch_code += f"{i1}case {val}:\n"
                                if body:
                                    # Add indentation to body lines
                                    lines = body.split('\n')
                                    indented_body = "\n".join(
                                        f"{i2}{line.strip()}" if line.strip() else ""
                                        for line in lines
                                    )
                                    switch_code += f"{indented_body}\n"
                                switch_code += f"{i2}break;\n"
                        else:
                            # nesting/fallthrough style: emit multiple labels then one shared body.
                            for val in vals:
                                switch_code += f"{i1}case {val}:\n"
                            if body:
                                lines = body.split('\n')
                                indented_body = "\n".join(
                                    f"{i2}{line.strip()}" if line.strip() else ""
                                    for line in lines
                                )
                                switch_code += f"{indented_body}\n"
                            switch_code += f"{i2}break;\n"
                    
                    if default_body is not None:
                        switch_code += f"{i1}default:\n"
                        if default_body:
                            lines = default_body.split('\n')
                            indented_body = "\n".join(f"{i2}{line.strip()}" if line.strip() else "" for line in lines)
                            switch_code += f"{indented_body}\n"
                        switch_code += f"{i2}break;\n"
                    
                    switch_code += f"{base_indent}}}"
                    
                    start = if_node.start_byte
                    end = if_node.end_byte
                    source_code = source_code[:start] + switch_code.encode('utf-8') + source_code[end:]
                    replaced = True
                    break 
                    
            if not replaced:
                break 

        return source_code.decode("utf-8")
