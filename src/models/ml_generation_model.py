import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class MLModelConfig:
    """Configuration for ML-based generation models."""
    similarity_threshold: float = 0.75
    auto_learn: bool = True
    index_path: Optional[str] = None
    top_k_retrieval: int = 3
    fallback_to_templates: bool = True

    use_llm: bool = True
    llm_model_name: Optional[str] = None
    llm_max_tokens: int = 1024
    llm_temperature: float = 0.2
    llm_use_few_shot: bool = True

    use_semantic_encoder: bool = True
    semantic_model_name: str = "microsoft/codebert-base"

    use_learning: bool = True
    learning_storage_path: Optional[str] = None
    learning_rate: float = 0.1
    reinforcement_discount: float = 0.9
    exploration_epsilon: float = 0.05


class RetrievalInfo:
    """Information about last retrieval operation."""
    def __init__(self, used_similarity: bool = True, similar_specs: int = 0, best_score: float = 0.0):
        self.used_similarity = used_similarity
        self.similar_specs = similar_specs
        self.best_score = best_score


class NameNormalizer:
    """Utility for normalizing and adapting design names in filenames and code."""

    DESIGN_NAME_PATTERN = re.compile(
        r"([a-zA-Z_][a-zA-Z0-9_]*?)_(driver|monitor|agent|sequencer|sequence_item|sequence|scoreboard|coverage_collector|env|test|interface|testbench|ral_model|serial_monitor)",
        re.IGNORECASE
    )

    @classmethod
    def adapt_names(
        cls,
        filename: str,
        old_design_name: str,
        new_design_name: str,
    ) -> str:
        """
        Adapt filenames and content from old design name to new design name.

        Args:
            filename: Original filename
            old_design_name: Old design name to replace
            new_design_name: New design name to use

        Returns:
            Adapted filename
        """
        if not old_design_name or not new_design_name:
            return filename

        old_lower = old_design_name.lower()
        new_lower = new_design_name.lower()

        base_name = filename
        ext = ""

        if "." in filename:
            parts = filename.rsplit(".", 1)
            base_name = parts[0]
            ext = "." + parts[1] if len(parts) > 1 else ""

        if old_lower in base_name.lower():
            new_base = re.sub(
                re.escape(old_design_name),
                new_design_name,
                base_name,
                flags=re.IGNORECASE,
            )
            return new_base + ext

        match = cls.DESIGN_NAME_PATTERN.match(base_name)
        if match:
            prefix = match.group(1)
            suffix = match.group(2)
            if prefix.lower() == old_lower:
                return f"{new_design_name}_{suffix}{ext}"

        return filename

    @classmethod
    def adapt_content(
        cls,
        content: str,
        old_design_name: str,
        new_design_name: str,
    ) -> str:
        """
        Adapt SystemVerilog content from old design name to new design name.

        Args:
            content: Original SystemVerilog content
            old_design_name: Old design name to replace
            new_design_name: New design name to use

        Returns:
            Adapted content
        """
        if not old_design_name or not new_design_name or old_design_name == new_design_name:
            return content

        result = content

        patterns = [
            (
                rf"\b{re.escape(old_design_name)}_([a-zA-Z_][a-zA-Z0-9_]*)\b",
                f"{new_design_name}_\\1",
            ),
            (
                rf"\bclass\s+{re.escape(old_design_name)}_",
                f"class {new_design_name}_",
            ),
            (
                rf"`uvm_component_utils\(\s*{re.escape(old_design_name)}_",
                f"`uvm_component_utils({new_design_name}_",
            ),
            (
                rf"`uvm_object_utils\(\s*{re.escape(old_design_name)}_",
                f"`uvm_object_utils({new_design_name}_",
            ),
            (
                rf"virtual\s+{re.escape(old_design_name)}_if\s+",
                f"virtual {new_design_name}_if ",
            ),
            (
                rf"{re.escape(old_design_name)}_if::type_id",
                f"{new_design_name}_if::type_id",
            ),
        ]

        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        result = re.sub(
            rf"\b{re.escape(old_design_name)}\b",
            new_design_name,
            result,
        )

        return result

    @classmethod
    def normalize_name(cls, name: str) -> str:
        """
        Normalize a design name to a standard format.

        - Converts to snake_case
        - Removes special characters
        - Ensures valid SystemVerilog identifier

        Args:
            name: Original name

        Returns:
            Normalized name
        """
        if not name:
            return "design"

        result = name.strip()

        result = re.sub(r"[^a-zA-Z0-9_]", "_", result)

        result = re.sub(r"_+", "_", result)

        result = result.strip("_")

        if not result:
            return "design"

        if not result[0].isalpha() and result[0] != "_":
            result = "_" + result

        return result.lower()


class MLGenerationModel:
    """
    ML-based generation model (legacy name for EnhancedMLGenerationModel).

    This class exists for backward compatibility with tests and code
    that imports MLGenerationModel. Use EnhancedMLGenerationModel directly
    for new code.
    """

    def __new__(cls, *args, **kwargs):
        from src.models.enhanced_ml_model import EnhancedMLGenerationModel
        return EnhancedMLGenerationModel(*args, **kwargs)
