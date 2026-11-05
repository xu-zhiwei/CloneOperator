"""Structured edits and application records."""
from dataclasses import dataclass, field


@dataclass
class Edit:
    start_byte: int
    end_byte: int
    replacement: str


@dataclass
class ApplicationResult:
    code: str
    strategy_id: str
    requested: int
    successful: int = 0
    changes: list = field(default_factory=list)
    rejections: list = field(default_factory=list)
    eligible_candidates: int = 0
    language: str = "java"
