"""Strategies in this SCT table category; compatible category exports."""
from .relational_expression_rewriting import RelationalExpressionRewriting
from .increment_decrement_rewriting import IncrementDecrementRewriting
from .compound_assignment_rewriting import CompoundAssignmentRewriting

__all__ = [
    "RelationalExpressionRewriting",
    "IncrementDecrementRewriting",
    "CompoundAssignmentRewriting",
]

from .increment_decrement_contraction import IncrementDecrementContraction
from .compound_assignment_contraction import CompoundAssignmentContraction
from .de_morgan_expansion import DeMorganExpansion
from .de_morgan_contraction import DeMorganContraction

__all__ = list(globals().get("__all__", [])) + ['IncrementDecrementContraction', 'CompoundAssignmentContraction', 'DeMorganExpansion', 'DeMorganContraction']
