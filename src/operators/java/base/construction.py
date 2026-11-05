"""Parser and formatting primitives used by structural constructors."""
from tree_sitter import Language, Parser
import tree_sitter_java as tsjava


class ConstructionBase:
    def __init__(self):
        # Initialize Parser and resolve compatibility issues between old and new versions
        self.JAVA_LANGUAGE = Language(tsjava.language())
        self.parser = Parser()
        if hasattr(self.parser, "set_language"):
            self.parser.set_language(self.JAVA_LANGUAGE)
        else:
            self.parser = Parser(self.JAVA_LANGUAGE)

    def _parse_code(self, code_bytes):
        """Use tree-sitter to parse the code and return the tree"""
        tree = self.parser.parse(bytes(code_bytes))
        return tree

    def _find_nodes_by_type(self, node, node_type):
        """Recursively find all nodes of the specified type in the AST"""
        nodes = []
        if type(node_type) is list:
            if node.type in node_type:
                nodes.append(node)
        else:
            if node.type == node_type:
                nodes.append(node)

        for child in node.children:
            nodes.extend(self._find_nodes_by_type(child, node_type))
        return nodes


class LoopConstructionBase(ConstructionBase):
    def _get_indent_and_labels(self, code_bytes, target_node):
        """
        Extract base indentation and labels for a given loop node.
        Returns:
            base_indent (str): The base indentation string.
            i1 (str): Base indentation + 4 spaces.
            i2 (str): Base indentation + 8 spaces.
            labels (list): List of label strings.
            node_to_replace (Node): The outermost labeled node (or the target node itself).
        """
        # === 0. Dynamically extract indentation ===
        line_start = code_bytes.rfind(b"\n", 0, target_node.start_byte)
        if line_start == -1:
            line_start = 0
        else:
            line_start += 1
        indent_bytes = code_bytes[line_start : target_node.start_byte]
        base_indent = "".join(chr(b) for b in indent_bytes if chr(b) in [" ", "\t"])
        i1 = base_indent + "    "
        i2 = i1 + "    "

        # === 1. Handle Labels ===
        labels = []
        node_to_replace = target_node
        curr = target_node.parent
        while curr and curr.type == "labeled_statement":
            label_node = curr.child_by_field_name("label")
            if not label_node and curr.named_children:
                label_node = curr.named_children[0]
            if label_node:
                labels.append(
                    code_bytes[label_node.start_byte : label_node.end_byte].decode(
                        "utf-8"
                    )
                )

            # Update indent based on the outermost label
            line_start = code_bytes.rfind(b"\n", 0, curr.start_byte)
            if line_start == -1:
                line_start = 0
            else:
                line_start += 1
            indent_bytes = code_bytes[line_start : curr.start_byte]
            base_indent = "".join(chr(b) for b in indent_bytes if chr(b) in [" ", "\t"])
            i1 = base_indent + "    "
            i2 = i1 + "    "

            node_to_replace = curr
            curr = curr.parent

        labels.reverse()
        return base_indent, i1, i2, labels, node_to_replace


class ConditionalConstructionBase(ConstructionBase):
    def _get_indent(self, code_bytes, target_node):
        """
        Extract base indentation for a given node.
        Returns:
            base_indent (str): The base indentation string.
            i1 (str): Base indentation + 4 spaces.
            i2 (str): Base indentation + 8 spaces.
        """
        line_start = code_bytes.rfind(b"\n", 0, target_node.start_byte)
        if line_start == -1:
            line_start = 0
        else:
            line_start += 1
        indent_bytes = code_bytes[line_start : target_node.start_byte]
        base_indent = "".join(chr(b) for b in indent_bytes if chr(b) in [" ", "\t"])
        i1 = base_indent + "    "
        i2 = i1 + "    "
        return base_indent, i1, i2
