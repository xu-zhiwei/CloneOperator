"""Public SCT registry, organized by level, target and transformation category."""
from operators.java.control.conditional.redundancy.redundant_branch_insertion import (
    RedundantBranchInsertion,
)
from operators.java.control.conditional.redundancy.redundant_branch_removal import (
    RedundantBranchRemoval,
)
from operators.java.control.conditional.reordering.independent_case_group_permutation import (
    IndependentCaseGroupPermutation,
)
from operators.java.control.conditional.replacement.if_to_switch_nesting import (
    IfToSwitchNesting,
)
from operators.java.control.conditional.replacement.if_to_switch_cloning import (
    IfToSwitchCloning,
)
from operators.java.control.conditional.replacement.switch_to_if_nesting import (
    SwitchToIfNesting,
)
from operators.java.control.conditional.replacement.switch_to_if_cloning import (
    SwitchToIfCloning,
)
from operators.java.control.conditional.replacement.conditional_nesting import (
    ConditionalNesting,
)
from operators.java.control.conditional.replacement.conditional_flattening import (
    ConditionalFlattening,
)
from operators.java.control.conditional.replacement.condition_inversion_and_branch_exchange import (
    ConditionInversionAndBranchExchange,
)
from operators.java.control.loop.redundancy.redundant_loop_insertion import (
    RedundantLoopInsertion,
)
from operators.java.control.loop.redundancy.redundant_loop_removal import (
    RedundantLoopRemoval,
)
from operators.java.control.loop.replacement.for_to_while import ForToWhile
from operators.java.control.loop.replacement.while_to_for import WhileToFor
from operators.java.control.loop.replacement.for_to_do_while import ForToDoWhile
from operators.java.control.loop.replacement.do_while_to_for import DoWhileToFor
from operators.java.control.loop.replacement.do_while_to_while import DoWhileToWhile
from operators.java.control.loop.replacement.while_to_do_while import WhileToDoWhile
from operators.java.statement.declaration.redundancy.redundant_declaration_insertion import (
    RedundantDeclarationInsertion,
)
from operators.java.statement.declaration.redundancy.redundant_declaration_removal import (
    RedundantDeclarationRemoval,
)
from operators.java.statement.declaration.reordering.declaration_exchange import (
    DeclarationExchange,
)
from operators.java.statement.declaration.replacement.declaration_splitting import (
    DeclarationSplitting,
)
from operators.java.statement.declaration.replacement.declaration_merging import (
    DeclarationMerging,
)
from operators.java.statement.expression.redundancy.expression_redundant_wrapping import (
    ExpressionRedundantWrapping,
)
from operators.java.statement.expression.redundancy.expression_redundant_unwrapping import (
    ExpressionRedundantUnwrapping,
)
from operators.java.statement.expression.reordering.operand_exchange import (
    OperandExchange,
)
from operators.java.statement.expression.replacement.relational_expression_rewriting import (
    RelationalExpressionRewriting,
)
from operators.java.statement.expression.replacement.increment_decrement_rewriting import (
    IncrementDecrementRewriting,
)
from operators.java.statement.expression.replacement.compound_assignment_rewriting import (
    CompoundAssignmentRewriting,
)
from operators.java.statement.ordinary_statement.redundancy.redundant_computation_insertion import (
    RedundantComputationInsertion,
)
from operators.java.statement.ordinary_statement.redundancy.redundant_computation_removal import (
    RedundantComputationRemoval,
)
from operators.java.statement.ordinary_statement.reordering.independent_computation_exchange import (
    IndependentComputationExchange,
)
from operators.java.statement.ordinary_statement.replacement.computation_splitting import (
    ComputationSplitting,
)
from operators.java.statement.ordinary_statement.replacement.computation_merging import (
    ComputationMerging,
)
from operators.java.word.constant.redundancy.constant_neutral_term_insertion import (
    ConstantNeutralTermInsertion,
)
from operators.java.word.constant.redundancy.constant_neutral_term_removal import (
    ConstantNeutralTermRemoval,
)
from operators.java.word.constant.replacement.integer_addition_decomposition import (
    IntegerAdditionDecomposition,
)
from operators.java.word.constant.replacement.boolean_negation_replacement import (
    BooleanNegationReplacement,
)
from operators.java.word.constant.replacement.integer_subtraction_representation import (
    IntegerSubtractionRepresentation,
)
from operators.java.word.identifier.replacement.identifier_renaming import (
    IdentifierRenaming,
)

from operators.taxonomy import TABLE, LOCATIONS, strategy_ids, RELATIONS, PAIRS, get_relation

from operators.java.word.constant.replacement.integer_addition_composition import IntegerAdditionComposition
from operators.java.word.constant.replacement.integer_subtraction_composition import IntegerSubtractionComposition
from operators.java.word.constant.replacement.boolean_negation_constant_reduction import BooleanNegationConstantReduction
from operators.java.statement.expression.replacement.increment_decrement_contraction import IncrementDecrementContraction
from operators.java.statement.expression.replacement.compound_assignment_contraction import CompoundAssignmentContraction
from operators.java.statement.expression.replacement.de_morgan_expansion import DeMorganExpansion
from operators.java.statement.expression.replacement.de_morgan_contraction import DeMorganContraction
from operators.java.control.conditional.replacement.conditional_expression_to_if import ConditionalExpressionToIf
from operators.java.control.conditional.replacement.if_to_conditional_expression import IfToConditionalExpression
from operators.java.control.conditional.replacement.disjunction_branch_splitting import DisjunctionBranchSplitting
from operators.java.control.conditional.replacement.disjunction_branch_merging import DisjunctionBranchMerging

STRATEGIES = (
    IdentifierRenaming,
    ConstantNeutralTermInsertion,
    ConstantNeutralTermRemoval,
    IntegerAdditionDecomposition,
    BooleanNegationReplacement,
    IntegerSubtractionRepresentation,
    OperandExchange,
    ExpressionRedundantWrapping,
    ExpressionRedundantUnwrapping,
    RelationalExpressionRewriting,
    IncrementDecrementRewriting,
    CompoundAssignmentRewriting,
    DeclarationExchange,
    RedundantDeclarationInsertion,
    RedundantDeclarationRemoval,
    DeclarationSplitting,
    DeclarationMerging,
    IndependentComputationExchange,
    RedundantComputationInsertion,
    RedundantComputationRemoval,
    ComputationSplitting,
    ComputationMerging,
    IndependentCaseGroupPermutation,
    RedundantBranchInsertion,
    RedundantBranchRemoval,
    IfToSwitchNesting,
    IfToSwitchCloning,
    SwitchToIfNesting,
    SwitchToIfCloning,
    ConditionalNesting,
    ConditionalFlattening,
    ConditionInversionAndBranchExchange,
    RedundantLoopInsertion,
    RedundantLoopRemoval,
    ForToWhile,
    WhileToFor,
    ForToDoWhile,
    DoWhileToFor,
    DoWhileToWhile,
    WhileToDoWhile,
    IntegerAdditionComposition,
    IntegerSubtractionComposition,
    BooleanNegationConstantReduction,
    IncrementDecrementContraction,
    CompoundAssignmentContraction,
    DeMorganExpansion,
    DeMorganContraction,
    ConditionalExpressionToIf,
    IfToConditionalExpression,
    DisjunctionBranchSplitting,
    DisjunctionBranchMerging,
)
REGISTRY = {cls.strategy_id: cls for cls in STRATEGIES}
STRATEGY_NAMES = {sid: cls.__name__ for sid, cls in REGISTRY.items()}


def get_registry(language="java"):
    if language == "java":
        return REGISTRY
    if language != "c":
        raise ValueError(f"Unknown SCT language: {language!r}")
    from importlib import import_module

    return {
        sid: getattr(
            import_module(cls.__module__.replace("operators.java.", "operators.c.")),
            cls.__name__,
        )
        for sid, cls in REGISTRY.items()
    }


def create_strategy(strategy_id, language="java", **kwargs):
    try:
        cls = get_registry(language)[strategy_id.upper()]
    except (KeyError, AttributeError):
        raise ValueError(f"Unknown SCT strategy: {strategy_id!r}") from None
    return cls(**kwargs)


__all__ = list(STRATEGY_NAMES.values()) + [
    "RELATIONS",
    "PAIRS",
    "get_relation",
    "TABLE",
    "LOCATIONS",
    "strategy_ids",
    "REGISTRY",
    "STRATEGY_NAMES",
    "create_strategy",
    "get_registry",
]
