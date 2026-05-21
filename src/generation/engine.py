# src/generation/engine.py — Generation engine (orchestrates model inference)

from __future__ import annotations

from typing import Dict, List, Optional

from src.config import DesignSpec, PipelineConfig
from src.models.base_model import GenerationModel
from src.models.template_model import TemplateModel
from src.utils.decorators import timer


class GenerationEngine:
    """Orchestrates TB generation using a 'model' (template or learned)."""

    def __init__(self, model: Optional[GenerationModel] = None):
        self.model = model or TemplateModel()

    @timer
    def generate(self, spec: DesignSpec, cfg: PipelineConfig,
                 extra_seqs: Optional[List[str]] = None) -> Dict[str, str]:
        if not self.model.is_trained:
            self.model.train([spec])
        return self.model.predict(spec, cfg, extra_seqs=extra_seqs)
