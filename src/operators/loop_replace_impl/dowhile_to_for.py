import re
from .base_loop_operator import BaseLoopOperator

class DoWhileToFor(BaseLoopOperator):
    COMMON_VAR_NAMES = [
        "flag", "p", "q", "ok", "done", "first", "state", "ready", "active", "keep"
    ]

    def __init__(self):
        super().__init__()

    def _select_common_var_name(self, code_text: str) -> str:
        for name in self.COMMON_VAR_NAMES:
            # Use token-boundary regex to avoid partial-word collisions.
            if not re.search(fr"\b{name}\b", code_text):
                return name

        # Fallback: append numeric suffix to a common base name.
        index = 1
        while re.search(fr"\bflag{index}\b", code_text):
            index += 1
        return f"flag{index}"

    def __call__(self, code: str) -> str:
        code_bytes = code.encode("utf-8")
        
        while True:
            tree = self._parse_code(code_bytes)
            root_node = tree.root_node

            loop_nodes = self._find_nodes_by_type(root_node, "do_statement")
            if not loop_nodes:
                break
                
            # Sort to ensure we always replace from the last/deepest node first
            loop_nodes.sort(key=lambda n: n.start_byte)
            target_node = loop_nodes[-1]

            base_indent, i1, i2, labels, node_to_replace = self._get_indent_and_labels(code_bytes, target_node)

            cond_node = target_node.child_by_field_name("condition")
            body_node = target_node.child_by_field_name("body")

            # === 2. Handle Condition ===
            cond_code = "true"
            if cond_node:
                cond_bytes = code_bytes[cond_node.start_byte:cond_node.end_byte].decode("utf-8").strip()
                # Strip the outer parentheses from the AST
                if cond_bytes.startswith('(') and cond_bytes.endswith(')'):
                    cond_code = cond_bytes[1:-1].strip()
                else:
                    cond_code = cond_bytes

            # === 3. Handle Body ===
            body_code = ""
            has_braces = False
            if body_node:
                raw_body_code = code_bytes[body_node.start_byte:body_node.end_byte].decode("utf-8")
                has_braces = raw_body_code.startswith("{") and raw_body_code.endswith("}")
                if has_braces: body_code = raw_body_code[1:-1].strip('\n\r').rstrip()
                else: body_code = raw_body_code.strip()

            # === 4. Assemble new For Loop ===
            new_code = "{\n"
            for lbl in labels:
                new_code += f"{i1}{lbl}:\n"

            # Use a common variable name and ensure it does not collide with existing identifiers.
            var_name = self._select_common_var_name(code_bytes.decode("utf-8"))
            new_code += f"{i1}for (boolean {var_name} = true; {var_name} || ({cond_code}); {var_name} = false) {{\n"
            if body_code:
                if has_braces: new_code += f"{body_code}\n"
                else: new_code += f"{i2}{body_code}\n"
            new_code += f"{i1}}}\n"

            new_code += f"{base_indent}}}"

            start_byte = node_to_replace.start_byte
            end_byte = node_to_replace.end_byte
            code_bytes = code_bytes[:start_byte] + new_code.encode("utf-8") + code_bytes[end_byte:]

        return code_bytes.decode("utf-8")
