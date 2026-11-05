"""Strategies in this SCT table category; compatible category exports."""
from .redundant_loop_insertion import RedundantLoopInsertion
from .redundant_loop_removal import RedundantLoopRemoval

__all__ = ["RedundantLoopInsertion", "RedundantLoopRemoval"]
