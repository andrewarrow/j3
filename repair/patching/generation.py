"""Compatibility exports for structured candidate generation.

The implementation lives under ``repair.patching.generators`` so individual
generator families can stay small while existing imports keep working.
"""

from .generators import generate_candidate_patches

__all__ = ["generate_candidate_patches"]
