"""Strategies in this SCT table category; compatible category exports."""
from .for_to_while import ForToWhile
from .while_to_for import WhileToFor
from .for_to_do_while import ForToDoWhile
from .do_while_to_for import DoWhileToFor
from .do_while_to_while import DoWhileToWhile
from .while_to_do_while import WhileToDoWhile

__all__ = [
    "ForToWhile",
    "WhileToFor",
    "ForToDoWhile",
    "DoWhileToFor",
    "DoWhileToWhile",
    "WhileToDoWhile",
]
