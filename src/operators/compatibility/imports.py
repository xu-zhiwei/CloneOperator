"""Central compatibility imports; no historical files or algorithms.

Table-driven aliases follow the canonical registry. Special historical names
are declared explicitly below and resolved to current implementations.
"""
from importlib import import_module
from importlib.machinery import ModuleSpec
from types import ModuleType
import sys
from operators.registry import REGISTRY
from operators.taxonomy import LOCATIONS

ALIASES = {
    "identifier_rename": {
        "IdentifierRename": ("operators.compatibility.adapters", "IdentifierRenameV4")
    },
    "base_operator": {
        "BaseOperator": ("operators.compatibility.adapters", "BaseOperator")
    },
    "condition_replace": {
        "ConditionReplace": ("operators.compatibility.adapters", "ConditionReplace")
    },
    "constant_replace": {
        "ConstantReplace": ("operators.compatibility.adapters", "ConstantReplace")
    },
    "constant_replace_v2": {
        "ConstantReplaceV2": ("operators.compatibility.adapters", "ConstantReplaceV2")
    },
    "identifier_rename_v1": {
        "IdentifierRenameV1": ("operators.compatibility.adapters", "IdentifierRenameV1")
    },
    "identifier_rename_v2": {
        "IdentifierRenameV2": ("operators.compatibility.adapters", "IdentifierRenameV2")
    },
    "identifier_rename_v3": {
        "IdentifierRenameV3": ("operators.compatibility.adapters", "IdentifierRenameV3")
    },
    "identifier_rename_v4": {
        "IdentifierRenameV4": ("operators.compatibility.adapters", "IdentifierRenameV4")
    },
    "identifier_rename_v5": {
        "IdentifierRenameV5": ("operators.compatibility.adapters", "IdentifierRenameV5")
    },
    "identifier_reorder": {
        "IdentifierReorder": ("operators.compatibility.adapters", "IdentifierReorder")
    },
    "loop_replace": {
        "LoopReplace": ("operators.compatibility.adapters", "LoopReplace")
    },
    "redundant_constant_insert": {
        "RedundantConstantInsert": (
            "operators.compatibility.adapters",
            "RedundantConstantInsert",
        )
    },
    "redundant_statement_insert": {
        "RedundantStatementInsert": (
            "operators.compatibility.adapters",
            "RedundantStatementInsert",
        )
    },
    "statement_reorder": {
        "StatementReorder": ("operators.compatibility.adapters", "StatementReorder")
    },
    "sct_core": {
        "walk": ("operators.tools.source", "walk"),
        "ancestor": ("operators.tools.source", "ancestor"),
        "unwrap": ("operators.tools.source", "unwrap"),
        "Edit": ("operators.base.results", "Edit"),
        "ApplicationResult": ("operators.base.results", "ApplicationResult"),
        "Context": ("operators.analysis.context", "Context"),
        "Strategy": ("operators.base.strategy", "Strategy"),
    },
    "sct_strategies": "operators.registry",
    "sct_taxonomy": "operators.taxonomy",
    "sct_impl.base": {
        "Candidate": ("operators.base.candidate", "Candidate"),
        "AnalyzedStrategy": ("operators.base.candidate", "AnalyzedStrategy"),
        "TypedSampler": ("operators.tools.sampling", "TypedSampler"),
        "load_statistics": ("operators.tools.sampling", "load_statistics"),
        "splice": ("operators.tools.editing", "splice"),
        "direct_block": ("operators.tools.editing", "direct_block"),
    },
    "sct_impl.analysis": {
        "INTEGRAL": ("operators.analysis.semantic", "INTEGRAL"),
        "NUMERIC": ("operators.analysis.semantic", "NUMERIC"),
        "PRIMITIVES": ("operators.analysis.semantic", "PRIMITIVES"),
        "BARRIERS": ("operators.analysis.semantic", "BARRIERS"),
        "COMMENTS": ("operators.analysis.semantic", "COMMENTS"),
        "contains": ("operators.analysis.semantic", "contains"),
        "statements": ("operators.analysis.semantic", "statements"),
        "Symbol": ("operators.analysis.semantic", "Symbol"),
        "Effects": ("operators.analysis.semantic", "Effects"),
        "SemanticContext": ("operators.analysis.semantic", "SemanticContext"),
        "walk": ("operators.analysis.semantic", "walk"),
        "completion_outcomes": ("operators.analysis.completion", "completion_outcomes"),
    },
    "sct_impl._legacy": {
        "LegacyConversion": ("operators.base.conversion", "ConversionStrategy")
    },
    "sct_impl.legacy": {
        "LegacyConversion": ("operators.base.conversion", "ConversionStrategy"),
        "IfToSwitchNesting": (
            "operators.control.conditional.replacement",
            "IfToSwitchNesting",
        ),
        "IfToSwitchCloning": (
            "operators.control.conditional.replacement",
            "IfToSwitchCloning",
        ),
        "SwitchToIfNesting": (
            "operators.control.conditional.replacement",
            "SwitchToIfNesting",
        ),
        "SwitchToIfCloning": (
            "operators.control.conditional.replacement",
            "SwitchToIfCloning",
        ),
        "ForToWhile": ("operators.control.loop.replacement", "ForToWhile"),
        "WhileToFor": ("operators.control.loop.replacement", "WhileToFor"),
        "ForToDoWhile": ("operators.control.loop.replacement", "ForToDoWhile"),
        "DoWhileToFor": ("operators.control.loop.replacement", "DoWhileToFor"),
    },
    "sct_impl.declarations": {
        "safe_initializer": (
            "operators.statement.declaration.tools",
            "safe_initializer",
        ),
        "DeclarationStrategy": (
            "operators.statement.declaration.tools",
            "DeclarationStrategy",
        ),
        "InsertionStrategy": (
            "operators.statement.declaration.tools",
            "InsertionStrategy",
        ),
        "DeclarationExchange": (
            "operators.statement.declaration.reordering",
            "DeclarationExchange",
        ),
        "RedundantDeclarationRemoval": (
            "operators.statement.declaration.redundancy",
            "RedundantDeclarationRemoval",
        ),
        "DeclarationSplitting": (
            "operators.statement.declaration.replacement",
            "DeclarationSplitting",
        ),
        "DeclarationMerging": (
            "operators.statement.declaration.replacement",
            "DeclarationMerging",
        ),
        "RedundantDeclarationInsertion": (
            "operators.statement.declaration.redundancy",
            "RedundantDeclarationInsertion",
        ),
    },
    "sct_impl.loops": {
        "loop_label": ("operators.control.loop.tools", "loop_label"),
        "continue_target": ("operators.control.loop.tools", "continue_target"),
        "always_abrupt": ("operators.control.loop.tools", "always_abrupt"),
        "LoopStrategy": ("operators.control.loop.tools", "LoopStrategy"),
        "DoWhileToWhile": ("operators.control.loop.replacement", "DoWhileToWhile"),
        "WhileToDoWhile": ("operators.control.loop.replacement", "WhileToDoWhile"),
        "RedundantLoopInsertion": (
            "operators.control.loop.redundancy",
            "RedundantLoopInsertion",
        ),
        "RedundantLoopRemoval": (
            "operators.control.loop.redundancy",
            "RedundantLoopRemoval",
        ),
    },
    "sct_impl.expressions": {
        "BinaryExpressionStrategy": (
            "operators.statement.expression.tools",
            "BinaryExpressionStrategy",
        ),
        "OperandExchange": (
            "operators.statement.expression.reordering",
            "OperandExchange",
        ),
        "ExpressionRedundantWrapping": (
            "operators.statement.expression.redundancy",
            "ExpressionRedundantWrapping",
        ),
        "ExpressionRedundantUnwrapping": (
            "operators.statement.expression.redundancy",
            "ExpressionRedundantUnwrapping",
        ),
        "RelationalExpressionRewriting": (
            "operators.statement.expression.replacement",
            "RelationalExpressionRewriting",
        ),
        "IncrementDecrementRewriting": (
            "operators.statement.expression.replacement",
            "IncrementDecrementRewriting",
        ),
        "CompoundAssignmentRewriting": (
            "operators.statement.expression.replacement",
            "CompoundAssignmentRewriting",
        ),
    },
    "sct_impl.computations": {
        "computational": (
            "operators.statement.ordinary_statement.tools",
            "computational",
        ),
        "value_expression": (
            "operators.statement.ordinary_statement.tools",
            "value_expression",
        ),
        "IndependentComputationExchange": (
            "operators.statement.ordinary_statement.reordering",
            "IndependentComputationExchange",
        ),
        "RedundantComputationInsertion": (
            "operators.statement.ordinary_statement.redundancy",
            "RedundantComputationInsertion",
        ),
        "RedundantComputationRemoval": (
            "operators.statement.ordinary_statement.redundancy",
            "RedundantComputationRemoval",
        ),
        "ComputationSplitting": (
            "operators.statement.ordinary_statement.replacement",
            "ComputationSplitting",
        ),
        "ComputationMerging": (
            "operators.statement.ordinary_statement.replacement",
            "ComputationMerging",
        ),
    },
    "sct_impl.identifiers": {
        "IdentifierRenaming": (
            "operators.word.identifier.replacement",
            "IdentifierRenaming",
        )
    },
    "sct_impl.conditionals": {
        "constant_boolean": ("operators.control.conditional.tools", "constant_boolean"),
        "checked_exception_risk": (
            "operators.control.conditional.tools",
            "checked_exception_risk",
        ),
        "terminates_group": ("operators.control.conditional.tools", "terminates_group"),
        "CaseGroup": ("operators.control.conditional.tools", "CaseGroup"),
        "ConditionalStrategy": (
            "operators.control.conditional.tools",
            "ConditionalStrategy",
        ),
        "IndependentCaseGroupPermutation": (
            "operators.control.conditional.reordering",
            "IndependentCaseGroupPermutation",
        ),
        "RedundantBranchInsertion": (
            "operators.control.conditional.redundancy",
            "RedundantBranchInsertion",
        ),
        "RedundantBranchRemoval": (
            "operators.control.conditional.redundancy",
            "RedundantBranchRemoval",
        ),
        "ConditionalNesting": (
            "operators.control.conditional.replacement",
            "ConditionalNesting",
        ),
        "ConditionalFlattening": (
            "operators.control.conditional.replacement",
            "ConditionalFlattening",
        ),
        "ConditionInversionAndBranchExchange": (
            "operators.control.conditional.replacement",
            "ConditionInversionAndBranchExchange",
        ),
    },
    "sct_impl.constants": {
        "IntegerLiteralStrategy": (
            "operators.word.constant.tools",
            "IntegerLiteralStrategy",
        ),
        "ConstantNeutralTermInsertion": (
            "operators.word.constant.redundancy",
            "ConstantNeutralTermInsertion",
        ),
        "ConstantNeutralTermRemoval": (
            "operators.word.constant.redundancy",
            "ConstantNeutralTermRemoval",
        ),
        "IntegerAdditionDecomposition": (
            "operators.word.constant.replacement",
            "IntegerAdditionDecomposition",
        ),
        "BooleanNegationReplacement": (
            "operators.word.constant.replacement",
            "BooleanNegationReplacement",
        ),
        "IntegerSubtractionRepresentation": (
            "operators.word.constant.replacement",
            "IntegerSubtractionRepresentation",
        ),
    },
    "sct_impl": {},
    "sct_impl.word.identifier._shared": {
        "Path": ("pathlib", "Path"),
        "AnalyzedStrategy": ("operators.base.candidate", "AnalyzedStrategy"),
        "Candidate": ("operators.base.candidate", "Candidate"),
        "TypedSampler": ("operators.tools.sampling", "TypedSampler"),
        "load_statistics": ("operators.tools.sampling", "load_statistics"),
        "walk": ("operators.tools.source", "walk"),
    },
    "condition_replace_impl.if_to_switch": {
        "IfToSwitch": (
            "operators.control.conditional.replacement.if_to_switch_nesting",
            "_IfToSwitchConstructor",
        )
    },
    "condition_replace_impl.switch_to_if": {
        "SwitchToIf": (
            "operators.control.conditional.replacement.switch_to_if_nesting",
            "_SwitchToIfConstructor",
        )
    },
    "loop_replace_impl.for_to_while": {
        "ForToWhile": (
            "operators.control.loop.replacement.for_to_while",
            "_ForToWhileConstructor",
        )
    },
    "loop_replace_impl.for_to_dowhile": {
        "ForToDoWhile": (
            "operators.control.loop.replacement.for_to_do_while",
            "_ForToDoWhileConstructor",
        )
    },
    "loop_replace_impl.while_to_for": {
        "WhileToFor": (
            "operators.control.loop.replacement.while_to_for",
            "_WhileToForConstructor",
        )
    },
    "loop_replace_impl.dowhile_to_for": {
        "DoWhileToFor": (
            "operators.control.loop.replacement.do_while_to_for",
            "_DoWhileToForConstructor",
        )
    },
    "condition_replace_impl": {},
    "loop_replace_impl": {},
    "condition_replace_impl.base_condition_operator": {
        "BaseConditionOperator": (
            "operators.base.construction",
            "ConditionalConstructionBase",
        )
    },
    "loop_replace_impl.base_loop_operator": {
        "BaseLoopOperator": ("operators.base.construction", "LoopConstructionBase")
    },
}

PACKAGES = {"sct_impl", "condition_replace_impl", "loop_replace_impl"}
for sid, cls in REGISTRY.items():
    flat = {"WI": "identifiers", "WC": "constants", "SE": "expressions", "SD": "declarations",
            "SS": "computations", "CC": "conditionals", "CL": "loops"}[sid[:2]]
    ALIASES.setdefault("sct_impl." + flat, {}).setdefault(cls.__name__, (cls.__module__, cls.__name__))
    location = LOCATIONS[sid]
    parts = (location.level, location.target, location.category)
    for depth in range(1, 4):
        relative = "sct_impl." + ".".join(parts[:depth])
        ALIASES[relative] = "operators." + ".".join(parts[:depth])
        PACKAGES.add(relative)
    suffix = cls.__module__.removeprefix("operators.java.")
    ALIASES["sct_impl." + suffix] = cls.__module__
    if location.target != "identifier":
        ALIASES["sct_impl." + ".".join(parts[:2]) + "._shared"] = (
            "operators." + ".".join(parts[:2]) + ".tools"
        )

LEGACY_EXPORTS = {
    "IdentifierRename": "identifier_rename",
    "BaseOperator": "base_operator",
    "ConditionReplace": "condition_replace",
    "ConstantReplace": "constant_replace",
    "IdentifierRenameV1": "identifier_rename_v1",
    "IdentifierRenameV2": "identifier_rename_v2",
    "IdentifierRenameV3": "identifier_rename_v3",
    "IdentifierRenameV4": "identifier_rename_v4",
    "IdentifierReorder": "identifier_reorder",
    "LoopReplace": "loop_replace",
    "RedundantConstantInsert": "redundant_constant_insert",
    "RedundantStatementInsert": "redundant_statement_insert",
    "StatementReorder": "statement_reorder",
}


def install_aliases():
    install_java_paths()
    for relative, target in sorted(
        ALIASES.items(), key=lambda item: item[0].count(".")
    ):
        fullname = "operators." + relative
        if fullname in sys.modules:
            continue
        module = ModuleType(
            fullname, "Compatibility alias for current SCT implementation."
        )
        module.__package__ = (
            fullname if relative in PACKAGES else fullname.rpartition(".")[0]
        )
        module.__spec__ = ModuleSpec(
            fullname, loader=None, is_package=relative in PACKAGES
        )
        if relative in PACKAGES:
            module.__path__ = []
        if isinstance(target, dict):
            module.__all__ = list(target)
        else:
            actual = import_module(target)
            module.__all__ = getattr(
                actual,
                "__all__",
                [name for name in vars(actual) if not name.startswith("_")],
            )

        def resolve(name, target=target, module=module):
            if name.startswith("__"):
                raise AttributeError(name)
            if isinstance(target, str):
                value = getattr(import_module(target), name)
            else:
                if name not in target:
                    raise AttributeError(name)
                path, attribute = target[name]
                value = getattr(import_module(path), attribute)
            setattr(module, name, value)
            return value

        module.__getattr__ = resolve
        sys.modules[fullname] = module
        parent, _, name = fullname.rpartition(".")
        if parent in sys.modules:
            setattr(sys.modules[parent], name, module)


def install_java_paths():
    """Map pre-language canonical paths to the exact Java module objects."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "java"
    for path in sorted(root.rglob("*.py"), key=lambda p: len(p.parts)):
        parts = path.relative_to(root).with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if not parts or parts in {("base",), ("tools",)}:
            continue
        suffix = ".".join(parts)
        actual = import_module("operators.java." + suffix)
        old = "operators." + suffix
        sys.modules.setdefault(old, actual)
        parent, _, name = old.rpartition(".")
        if parent in sys.modules:
            setattr(sys.modules[parent], name, actual)
