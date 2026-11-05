"""Strategies in this SCT table category; compatible category exports."""
from .redundant_declaration_insertion import RedundantDeclarationInsertion
from .redundant_declaration_removal import RedundantDeclarationRemoval

__all__ = ["RedundantDeclarationInsertion", "RedundantDeclarationRemoval"]
