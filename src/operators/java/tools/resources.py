"""Repository resource locations independent of strategy nesting."""
from pathlib import Path


def statistics_path():
    return (
        Path(__file__).resolve().parents[4] / "data" / "variable_frequency_stats.json"
    )
