"""
Similarity Index for UVM specification retrieval.
Enables finding similar specs to enable retrieval-augmented generation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.models.ml_utils import (
    RichFeatureVector,
    SearchResult,
    combined_similarity,
    HybridVectorizer,
)

logger = logging.getLogger("uvmgen")


@dataclass
class IndexEntry:
    """Entry in the similarity index."""

    fingerprint: str
    design_name: str
    protocol_type: Optional[str]
    feature_vector: RichFeatureVector
    spec_dict: Dict[str, Any]
    text_repr: str
    generated_files: Dict[str, str] = field(default_factory=dict)


class SimilarityIndex:
    """
    Similarity index for UVM specifications.

    Supports:
    - Adding specs to the index
    - Searching for similar specs
    - Persistence to disk
    - Hybrid similarity (structural + text-based)
    """

    def __init__(self, persist_path: Optional[str] = None):
        self._entries: Dict[str, IndexEntry] = {}
        self._vectorizer: Optional[HybridVectorizer] = None
        self._tfidf_vectors: List[Any] = []
        self._fingerprints_ordered: List[str] = []
        self._persist_path = Path(persist_path) if persist_path else None
        self._needs_reindex = False

    def add(
        self,
        feature_vector: RichFeatureVector,
        spec_dict: Dict[str, Any],
        generated_files: Optional[Dict[str, str]] = None,
    ) -> str:
        """Add a spec to the index."""
        fp = feature_vector.fingerprint()

        if fp in self._entries:
            logger.debug("Spec %s already in index, updating", fp)
            self._entries[fp].generated_files = generated_files or {}
            return fp

        entry = IndexEntry(
            fingerprint=fp,
            design_name=feature_vector.design_name,
            protocol_type=feature_vector.protocol_type,
            feature_vector=feature_vector,
            spec_dict=spec_dict,
            text_repr=feature_vector.to_text_repr(),
            generated_files=generated_files or {},
        )

        self._entries[fp] = entry
        self._needs_reindex = True
        logger.info("Added spec '%s' (%s) to index", entry.design_name, fp)
        return fp

    def _reindex(self) -> None:
        """Rebuild TF-IDF vectors from entries."""
        if not self._needs_reindex and self._vectorizer is not None:
            return

        if not self._entries:
            self._vectorizer = None
            self._tfidf_vectors = []
            self._fingerprints_ordered = []
            self._needs_reindex = False
            return

        self._fingerprints_ordered = list(self._entries.keys())
        texts = [self._entries[fp].text_repr for fp in self._fingerprints_ordered]

        self._vectorizer = HybridVectorizer()
        self._tfidf_vectors = self._vectorizer.fit_transform(texts)
        self._needs_reindex = False
        logger.debug("Reindexed %d specs", len(self._entries))

    def search(
        self,
        query: RichFeatureVector,
        top_k: int = 5,
        min_similarity: float = 0.2,
        use_text_similarity: bool = True,
    ) -> List[SearchResult]:
        """
        Search for similar specs.

        Args:
            query: RichFeatureVector of the query spec
            top_k: Maximum number of results to return
            min_similarity: Minimum similarity threshold (0.0-1.0)
            use_text_similarity: Whether to use TF-IDF text similarity

        Returns:
            List of SearchResult sorted by similarity (highest first)
        """
        if not self._entries:
            return []

        self._reindex()

        scores: List[Tuple[str, float]] = []

        if use_text_similarity and self._vectorizer is not None:
            query_text = query.to_text_repr()
            query_vec = self._vectorizer.transform([query_text])

            query_has_data = query_vec is not None
            if query_has_data:
                if hasattr(query_vec, 'shape'):
                    query_has_data = query_vec.shape[0] > 0
                elif hasattr(query_vec, '__len__'):
                    try:
                        query_has_data = len(query_vec) > 0
                    except TypeError:
                        query_has_data = True
                else:
                    query_has_data = True

            if self._vectorizer is not None and query_has_data:
                text_scores = self._vectorizer.similarity_matrix(
                    query_vec, self._tfidf_vectors
                )

                for idx, fp in enumerate(self._fingerprints_ordered):
                    entry = self._entries[fp]
                    struct_score = combined_similarity(query, entry.feature_vector)
                    text_score = text_scores[idx] if idx < len(text_scores) else 0.0

                    hybrid_score = struct_score * 0.6 + text_score * 0.4
                    if hybrid_score >= min_similarity:
                        scores.append((fp, hybrid_score))
        else:
            for fp, entry in self._entries.items():
                sim = combined_similarity(query, entry.feature_vector)
                if sim >= min_similarity:
                    scores.append((fp, sim))

        scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for rank, (fp, score) in enumerate(scores[:top_k]):
            entry = self._entries[fp]
            results.append(
                SearchResult(
                    fingerprint=fp,
                    design_name=entry.design_name,
                    protocol_type=entry.protocol_type,
                    similarity=score,
                    spec_dict=entry.spec_dict,
                    generated_files=entry.generated_files,
                    rank=rank,
                )
            )

        return results

    def get(self, fingerprint: str) -> Optional[IndexEntry]:
        """Get an entry by fingerprint."""
        return self._entries.get(fingerprint)

    def remove(self, fingerprint: str) -> bool:
        """Remove an entry from the index."""
        if fingerprint in self._entries:
            del self._entries[fingerprint]
            self._needs_reindex = True
            return True
        return False

    def clear(self) -> None:
        """Clear the entire index."""
        self._entries.clear()
        self._vectorizer = None
        self._tfidf_vectors = []
        self._fingerprints_ordered = []
        self._needs_reindex = False

    def __len__(self) -> int:
        return len(self._entries)

    def save(self, path: Optional[str] = None) -> None:
        """Save the index to disk as JSON."""
        save_path = Path(path) if path else self._persist_path
        if not save_path:
            raise ValueError("No persist_path configured and no path provided")

        data = {
            "version": "1.0",
            "entries": [],
        }

        for fp, entry in self._entries.items():
            entry_data = {
                "fingerprint": entry.fingerprint,
                "design_name": entry.design_name,
                "protocol_type": entry.protocol_type,
                "feature_vector": entry.feature_vector.to_dict(),
                "spec_dict": entry.spec_dict,
                "text_repr": entry.text_repr,
                "generated_files": entry.generated_files,
            }
            data["entries"].append(entry_data)

        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info("Saved index with %d entries to %s", len(self._entries), save_path)

    @classmethod
    def load(cls, path: str) -> "SimilarityIndex":
        """Load an index from disk."""
        load_path = Path(path)
        if not load_path.exists():
            logger.warning("Index file not found: %s, creating empty index", path)
            return cls(persist_path=path)

        with open(load_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        idx = cls(persist_path=path)

        for entry_data in data.get("entries", []):
            fv_dict = entry_data.get("feature_vector", {})
            fv = RichFeatureVector(
                interface_count=fv_dict.get("interface_count", 0),
                total_signals=fv_dict.get("total_signals", 0),
                register_count=fv_dict.get("register_count", 0),
                total_fields=fv_dict.get("total_fields", 0),
                complexity_score=fv_dict.get("complexity_score", 0.0),
                protocol_type=fv_dict.get("protocol_type"),
                signal_names=fv_dict.get("signal_names", []),
                signal_directions=fv_dict.get("signal_directions", {}),
                signal_widths=fv_dict.get("signal_widths", {}),
                register_names=fv_dict.get("register_names", []),
                register_addresses=fv_dict.get("register_addresses", {}),
                register_fields=fv_dict.get("register_fields", {}),
                register_access=fv_dict.get("register_access", {}),
                interface_names=fv_dict.get("interface_names", []),
                design_name=fv_dict.get("design_name", ""),
            )

            idx.add(
                feature_vector=fv,
                spec_dict=entry_data.get("spec_dict", {}),
                generated_files=entry_data.get("generated_files", {}),
            )

        logger.info("Loaded index with %d entries from %s", len(idx), load_path)
        return idx

    def all_entries(self) -> List[IndexEntry]:
        """Get all entries in the index."""
        return list(self._entries.values())


_global_index: Optional[SimilarityIndex] = None


def get_global_index() -> SimilarityIndex:
    """Get the global singleton index."""
    global _global_index
    if _global_index is None:
        _global_index = SimilarityIndex()
    return _global_index


def set_global_index(index: SimilarityIndex) -> None:
    """Set the global singleton index."""
    global _global_index
    _global_index = index
