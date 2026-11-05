"""Paper-numbered access to the 51 Java/C transformations."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from operators import create_strategy
from .batch import BatchComposer

PROFILE = "C_ENTRY_INSERTIONS_V2"
_ROOT = Path(__file__).resolve().parent
_INVENTORY = json.loads((_ROOT / "operators.json").read_text(encoding="utf-8"))
_ROWS = {row["paper_id"]: row for row in _INVENTORY["operators"]}


def list_operators():
    """Return paper IDs, taxonomy, and explicit implementation mappings."""
    return deepcopy(_INVENTORY["operators"])


def create_operator(paper_id, language="java", seed=42, **options):
    """Create one operator using the numbering in the paper.

    The underlying ApplicationResult.strategy_id is an implementation ID.
    Nine IDs differ from paper IDs; consult list_operators() for the mapping.
    """
    paper_id = paper_id.upper()
    if paper_id not in _ROWS:
        raise ValueError(f"Unknown paper operator ID: {paper_id!r}")
    return create_strategy(
        _ROWS[paper_id]["implementation_id"], language=language, seed=seed, **options
    )


def compose_all51(source, language="java", seed=42, program_id=None):
    """Apply the frozen finite batch schedule and return code and edit trace.

    Each call owns its strategies and composer state. The default program ID
    is the SHA-256 of the UTF-8 input, as in the C coverage experiment.
    """
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    config = json.loads((_ROOT / "all51.json").read_text(encoding="utf-8"))
    config["seed"] = seed
    program_id = (hashlib.sha256(source.encode("utf-8")).hexdigest()
                  if program_id is None else str(program_id))
    strategies = {pid: create_operator(pid, language=language, seed=seed)
                  for pid in _ROWS}
    result = BatchComposer(_ROWS, strategies, config, program_id).compose(source)
    result.update(language=language, seed=seed, composition=config["name"],
                  operator_profile=PROFILE if language == "c" else "SCT51_JAVA")
    return result


__all__ = ["PROFILE", "list_operators", "create_operator", "compose_all51"]
