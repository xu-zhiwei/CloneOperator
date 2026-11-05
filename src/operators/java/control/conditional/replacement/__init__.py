"""Strategies in this SCT table category; compatible category exports."""
from .if_to_switch_nesting import IfToSwitchNesting
from .if_to_switch_cloning import IfToSwitchCloning
from .switch_to_if_nesting import SwitchToIfNesting
from .switch_to_if_cloning import SwitchToIfCloning
from .conditional_nesting import ConditionalNesting
from .conditional_flattening import ConditionalFlattening
from .condition_inversion_and_branch_exchange import ConditionInversionAndBranchExchange

__all__ = [
    "IfToSwitchNesting",
    "IfToSwitchCloning",
    "SwitchToIfNesting",
    "SwitchToIfCloning",
    "ConditionalNesting",
    "ConditionalFlattening",
    "ConditionInversionAndBranchExchange",
]

from .conditional_expression_to_if import ConditionalExpressionToIf
from .if_to_conditional_expression import IfToConditionalExpression
from .disjunction_branch_splitting import DisjunctionBranchSplitting
from .disjunction_branch_merging import DisjunctionBranchMerging

__all__ = list(globals().get("__all__", [])) + ['ConditionalExpressionToIf', 'IfToConditionalExpression', 'DisjunctionBranchSplitting', 'DisjunctionBranchMerging']
