from .base_loop_operator import BaseLoopOperator

class ForToWhile(BaseLoopOperator):
    def __init__(self):
        super().__init__()

    def __call__(self, code: str) -> str:
        code_bytes = code.encode("utf-8")
        
        while True:
            tree = self._parse_code(code_bytes)
            root_node = tree.root_node

            for_stmt_nodes = self._find_nodes_by_type(root_node, "for_statement")
            if not for_stmt_nodes:
                break

            for_stmt_node = for_stmt_nodes[-1]

            base_indent, i1, i2, labels, node_to_replace = self._get_indent_and_labels(code_bytes, for_stmt_node)

            inits = []
            updates = []
            cond_node = None
            body_node = None

            cursor = for_stmt_node.walk()
            if cursor.goto_first_child():
                while True:
                    try: field = cursor.field_name
                    except AttributeError: field = cursor.current_field_name()

                    if field == "init": inits.append(cursor.node)
                    elif field == "condition": cond_node = cursor.node
                    elif field == "update": updates.append(cursor.node)
                    elif field == "body": body_node = cursor.node

                    if not cursor.goto_next_sibling():
                        break

            # === 2. Handle Init ===
            init_statements = []
            for node in inits:
                c = code_bytes[node.start_byte : node.end_byte].decode("utf-8").strip()
                if c:
                    if not c.endswith(";"): c += ";"
                    init_statements.append(c)

            # === 3. Handle Condition ===
            cond_code = "true"
            if cond_node:
                cond_code = code_bytes[cond_node.start_byte : cond_node.end_byte].decode("utf-8").strip()

            # === 4. Handle Update ===
            update_statements = []
            for node in updates:
                c = code_bytes[node.start_byte : node.end_byte].decode("utf-8").strip()
                if c:
                    if not c.endswith(";"): c += ";"
                    update_statements.append(c)

            # === 5. Handle Body and intercept continue ===
            body_code = ""
            has_braces = False
            
            if body_node:
                body_bytes_segment = code_bytes[body_node.start_byte : body_node.end_byte]
                if update_statements:
                    cont_nodes = self._find_nodes_by_type(body_node, "continue_statement")
                    cont_nodes.sort(key=lambda n: n.start_byte, reverse=True)

                    for cont_node in cont_nodes:
                        targets_us = False
                        cont_label_node = cont_node.child_by_field_name("label")
                        if not cont_label_node and cont_node.named_children:
                            cont_label_node = cont_node.named_children[0]

                        if cont_label_node:
                            cont_label = code_bytes[cont_label_node.start_byte : cont_label_node.end_byte].decode("utf-8")
                            if cont_label in labels: targets_us = True
                        else:
                            curr = cont_node.parent
                            while curr and curr != for_stmt_node:
                                if curr.type in ["for_statement", "while_statement", "do_statement", "enhanced_for_statement"]:
                                    break
                                curr = curr.parent
                            if curr == for_stmt_node: targets_us = True

                        if targets_us:
                            rel_start = cont_node.start_byte - body_node.start_byte
                            rel_end = cont_node.end_byte - body_node.start_byte

                            orig_cont = body_bytes_segment[rel_start:rel_end].decode("utf-8")
                            update_str = " ".join(update_statements)
                            patched_cont = f"{{ {update_str} {orig_cont} }}"
                            body_bytes_segment = body_bytes_segment[:rel_start] + patched_cont.encode("utf-8") + body_bytes_segment[rel_end:]

                raw_body_code = body_bytes_segment.decode("utf-8")
                has_braces = raw_body_code.startswith("{") and raw_body_code.endswith("}")
                if has_braces: body_code = raw_body_code[1:-1].strip('\n\r').rstrip()
                else: body_code = raw_body_code.strip()

            # === 6. Assemble new loop ===
            new_code = "{\n"
            for stmt in init_statements: new_code += f"{i1}{stmt}\n"
            for lbl in labels: new_code += f"{i1}{lbl}:\n"
            new_code += f"{i1}while ({cond_code}) {{\n"
            
            if body_code:
                if has_braces: new_code += f"{body_code}\n"
                else: new_code += f"{i2}{body_code}\n"
                    
            for stmt in update_statements: new_code += f"{i2}{stmt}\n"
            new_code += f"{i1}}}\n"
            new_code += f"{base_indent}}}"

            start_byte = node_to_replace.start_byte
            end_byte = node_to_replace.end_byte
            code_bytes = code_bytes[:start_byte] + new_code.encode("utf-8") + code_bytes[end_byte:]

        return code_bytes.decode("utf-8")
