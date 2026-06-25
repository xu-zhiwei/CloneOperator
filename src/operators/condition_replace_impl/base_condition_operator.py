import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from ..base_operator import BaseOperator

class BaseConditionOperator(BaseOperator):
    def __init__(self):
        super().__init__()
        # Initialize Parser and resolve compatibility issues between old and new versions
        self.JAVA_LANGUAGE = Language(tsjava.language())
        self.parser = Parser()
        if hasattr(self.parser, 'set_language'):
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

    def _get_indent(self, code_bytes, target_node):
        """
        Extract base indentation for a given node.
        Returns:
            base_indent (str): The base indentation string.
            i1 (str): Base indentation + 4 spaces.
            i2 (str): Base indentation + 8 spaces.
        """
        line_start = code_bytes.rfind(b'\n', 0, target_node.start_byte)
        if line_start == -1: 
            line_start = 0
        else: 
            line_start += 1
        indent_bytes = code_bytes[line_start:target_node.start_byte]
        base_indent = "".join(chr(b) for b in indent_bytes if chr(b) in [' ', '\t'])
        i1 = base_indent + "    "
        i2 = i1 + "    "
        return base_indent, i1, i2
