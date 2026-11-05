"""SCT strategies, classification and lazy public compatibility exports."""
from importlib import import_module
from .base.results import ApplicationResult
from .registry import *
from .registry import __all__ as _strategy_exports
from .compatibility.imports import install_aliases, LEGACY_EXPORTS

install_aliases()
_legacy = LEGACY_EXPORTS


def __getattr__(name):
    if name in _legacy or name in {"ConstantReplaceV2", "IdentifierRenameV5"}:
        value = getattr(import_module("operators.compatibility.adapters"), name)
        globals()[name] = value
        return value
    raise AttributeError(name)


__all__ = (
    list(_legacy)
    + _strategy_exports
    + ["ApplicationResult", "ConstantReplaceV2", "IdentifierRenameV5"]
)
