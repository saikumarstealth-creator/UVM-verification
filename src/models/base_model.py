# src/models/base_model.py — Abstract base for all generation models

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from src.config import DesignSpec, PipelineConfig


class GenerationModel(ABC):
    """Abstract base class for TB generation 'models'.

    Follows the ML paradigm:
      - train(data) -> learns templates / patterns from existing TBs
      - predict(spec) -> generates TB files for a new design
      - save(path) / load(path) -> serialisation
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._is_trained = False

    @property
    def is_trained(self) -> bool:
        return self._is_trained

    @abstractmethod
    def train(self, specs: List[DesignSpec]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def predict(self, spec: DesignSpec, cfg: PipelineConfig,
                extra_seqs: Optional[List[str]] = None) -> Dict[str, str]:
        ...

    @abstractmethod
    def save(self, path: str) -> None:
        ...

    @classmethod
    @abstractmethod
    def load(cls, path: str) -> "GenerationModel":
        ...
