"""Strategies in this SCT table category; compatible category exports."""
from .redundant_computation_insertion import RedundantComputationInsertion
from .redundant_computation_removal import RedundantComputationRemoval

__all__ = ["RedundantComputationInsertion", "RedundantComputationRemoval"]
