"""Abstract scoring interface.

`WeightedRiskModel` (weighted_model.py) is the v2 implementation: a fully
transparent, hand-weighted formula, configured by weights.json. It is
explicitly NOT machine learning.
A future `SklearnRiskModel` could implement this same interface (trained on
historical incidence data with a time-aware split, evaluated against this
baseline, explained via permutation importance/SHAP) and be swapped in
without changing the API layer or frontend, as long as it returns the same
ScoreResult shape.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas import FeatureSet, ScoreResult


class RiskModel(ABC):
    name: str

    @abstractmethod
    def score(self, features: FeatureSet) -> ScoreResult:
        """Compute a 0-100 score + label + explainable per-factor breakdown."""
        raise NotImplementedError
