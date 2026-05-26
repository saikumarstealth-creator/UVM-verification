"""
ML utilities for UVM testbench generation.
Lightweight implementation with optional numpy/scikit-learn acceleration.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Try optional dependencies
try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity as skl_cosine_similarity

    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


@dataclass
class RichFeatureVector:
    """Rich feature vector for ML-based similarity and generation."""

    interface_count: int = 0
    total_signals: int = 0
    register_count: int = 0
    total_fields: int = 0
    complexity_score: float = 0.0
    protocol_type: Optional[str] = None

    signal_names: List[str] = field(default_factory=list)
    signal_directions: Dict[str, str] = field(default_factory=dict)
    signal_widths: Dict[str, int] = field(default_factory=dict)

    register_names: List[str] = field(default_factory=list)
    register_addresses: Dict[str, str] = field(default_factory=dict)
    register_fields: Dict[str, List[str]] = field(default_factory=dict)
    register_access: Dict[str, str] = field(default_factory=dict)

    interface_names: List[str] = field(default_factory=list)

    design_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interface_count": self.interface_count,
            "total_signals": self.total_signals,
            "register_count": self.register_count,
            "total_fields": self.total_fields,
            "complexity_score": self.complexity_score,
            "protocol_type": self.protocol_type,
            "signal_names": self.signal_names,
            "signal_directions": self.signal_directions,
            "signal_widths": self.signal_widths,
            "register_names": self.register_names,
            "register_addresses": self.register_addresses,
            "register_fields": self.register_fields,
            "register_access": self.register_access,
            "interface_names": self.interface_names,
            "design_name": self.design_name,
        }

    def to_numerical(self) -> List[float]:
        """Convert to numerical vector for similarity computation."""
        vec = [
            float(self.interface_count),
            float(self.total_signals),
            float(self.register_count),
            float(self.total_fields),
            self.complexity_score,
        ]

        hashes = [
            hash_str(self.protocol_type or "none"),
            hash_str(",".join(sorted(self.signal_names))),
            hash_str(",".join(sorted(self.register_names))),
            hash_str(",".join(sorted(self.interface_names))),
        ]
        vec.extend([h / (2**32) for h in hashes])

        return vec

    def to_text_repr(self) -> str:
        """Convert to a text representation for TF-IDF encoding."""
        parts = []
        parts.append(f"protocol:{self.protocol_type or 'generic'}")
        parts.append(f"design:{self.design_name}")

        for name in self.signal_names:
            dir = self.signal_directions.get(name, "unknown")
            width = self.signal_widths.get(name, 1)
            parts.append(f"signal:{name}:{dir}:{width}")

        for name in self.register_names:
            access = self.register_access.get(name, "rw")
            fields = self.register_fields.get(name, [])
            parts.append(f"reg:{name}:{access}")
            for field in fields:
                parts.append(f"field:{name}.{field}")

        for name in self.interface_names:
            parts.append(f"interface:{name}")

        return " ".join(parts)

    def fingerprint(self) -> str:
        """Generate a stable fingerprint for this spec."""
        text = self.to_text_repr()
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def hash_str(s: str) -> int:
    """Hash a string to a 32-bit integer."""
    return int(hashlib.md5(s.encode("utf-8")).hexdigest()[:8], 16)


def cosine_similarity_py(v1: List[float], v2: List[float]) -> float:
    """Pure Python cosine similarity."""
    if len(v1) != len(v2):
        return 0.0

    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot / (norm1 * norm2)


def jaccard_similarity(set1: set, set2: set) -> float:
    """Jaccard similarity between two sets."""
    if not set1 and not set2:
        return 1.0
    union = set1 | set2
    if not union:
        return 0.0
    return len(set1 & set2) / len(union)


def weighted_signal_similarity(fv1: RichFeatureVector, fv2: RichFeatureVector) -> float:
    """Signal-based similarity with direction/width awareness."""
    signals1 = set(fv1.signal_names)
    signals2 = set(fv2.signal_names)

    if not signals1 or not signals2:
        return 0.0

    common = signals1 & signals2
    if not common:
        return 0.0

    score = 0.0
    max_score = 0.0

    for sig in common:
        max_score += 1.0
        dir1 = fv1.signal_directions.get(sig)
        dir2 = fv2.signal_directions.get(sig)
        w1 = fv1.signal_widths.get(sig, 1)
        w2 = fv2.signal_widths.get(sig, 1)

        if dir1 == dir2:
            score += 0.4
        else:
            score += 0.2

        if w1 == w2:
            score += 0.4
        else:
            score += 0.2

    coverage = len(common) / max(len(signals1), len(signals2))
    base_score = score / max_score if max_score > 0 else 0.0

    return base_score * 0.7 + coverage * 0.3


def protocol_similarity(fv1: RichFeatureVector, fv2: RichFeatureVector) -> float:
    """Protocol-based similarity."""
    p1 = fv1.protocol_type
    p2 = fv2.protocol_type

    if p1 and p2 and p1 == p2:
        return 1.0
    if p1 is None and p2 is None:
        return 0.5

    PROTOCOL_GROUPS = {
        "serial": {"uart", "spi", "i2c"},
        "bus": {"axi4lite", "apb", "wishbone"},
    }

    for group, members in PROTOCOL_GROUPS.items():
        if p1 in members and p2 in members:
            return 0.7

    return 0.1


def register_similarity(fv1: RichFeatureVector, fv2: RichFeatureVector) -> float:
    """Register structure similarity."""
    regs1 = set(fv1.register_names)
    regs2 = set(fv2.register_names)

    if not regs1 and not regs2:
        return 0.5

    jaccard = jaccard_similarity(regs1, regs2)

    access_match = 0.0
    common_regs = regs1 & regs2
    for reg in common_regs:
        a1 = fv1.register_access.get(reg, "rw")
        a2 = fv2.register_access.get(reg, "rw")
        if a1 == a2:
            access_match += 1.0

    access_score = access_match / len(common_regs) if common_regs else 0.0

    return jaccard * 0.6 + access_score * 0.4


def combined_similarity(fv1: RichFeatureVector, fv2: RichFeatureVector) -> float:
    """Combined similarity score across all dimensions."""
    proto_sim = protocol_similarity(fv1, fv2)
    signal_sim = weighted_signal_similarity(fv1, fv2)
    reg_sim = register_similarity(fv1, fv2)

    num1 = fv1.to_numerical()
    num2 = fv2.to_numerical()
    if HAS_SKLEARN and HAS_NUMPY:
        v1 = np.array(num1).reshape(1, -1)
        v2 = np.array(num2).reshape(1, -1)
        num_sim = float(skl_cosine_similarity(v1, v2)[0][0])
    else:
        num_sim = cosine_similarity_py(num1, num2)

    weights = {
        "protocol": 0.35,
        "signal": 0.30,
        "register": 0.20,
        "numerical": 0.15,
    }

    total = (
        proto_sim * weights["protocol"]
        + signal_sim * weights["signal"]
        + reg_sim * weights["register"]
        + num_sim * weights["numerical"]
    )

    return max(0.0, min(1.0, total))


@dataclass
class SearchResult:
    """Result from a similarity search."""

    fingerprint: str
    design_name: str
    protocol_type: Optional[str]
    similarity: float
    spec_dict: Dict[str, Any]
    generated_files: Dict[str, str] = field(default_factory=dict)
    rank: int = 0


class LightweightTFIDF:
    """Pure Python lightweight TF-IDF for text-based similarity."""

    def __init__(self):
        self.idf: Dict[str, float] = {}
        self.vocab: Dict[str, int] = {}
        self.doc_count = 0

    def fit(self, documents: List[str]) -> "LightweightTFIDF":
        """Fit on documents."""
        doc_freq: Dict[str, int] = defaultdict(int)
        self.doc_count = len(documents)

        vocab_set = set()
        for doc in documents:
            tokens = self._tokenize(doc)
            unique_tokens = set(tokens)
            for token in unique_tokens:
                doc_freq[token] += 1
            vocab_set.update(unique_tokens)

        self.vocab = {tok: idx for idx, tok in enumerate(sorted(vocab_set))}

        for token, df in doc_freq.items():
            self.idf[token] = math.log(self.doc_count / (df + 1)) + 1

        return self

    def transform(self, documents: List[str]) -> List[Dict[int, float]]:
        """Transform documents to TF-IDF vectors (sparse dict format)."""
        results = []
        for doc in documents:
            tokens = self._tokenize(doc)
            tf = Counter(tokens)
            total = len(tokens) if tokens else 1

            vec: Dict[int, float] = {}
            for token, count in tf.items():
                if token in self.vocab and token in self.idf:
                    tf_val = count / total
                    tfidf = tf_val * self.idf[token]
                    vec[self.vocab[token]] = tfidf
            results.append(vec)
        return results

    def fit_transform(self, documents: List[str]) -> List[Dict[int, float]]:
        return self.fit(documents).transform(documents)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        tokens = []
        for word in text.lower().split():
            for part in word.replace(":", " ").replace(".", " ").split():
                if part:
                    tokens.append(part)
        return tokens

    @staticmethod
    def cosine_sparse(v1: Dict[int, float], v2: Dict[int, float]) -> float:
        """Cosine similarity between two sparse vectors."""
        common_keys = set(v1.keys()) & set(v2.keys())
        if not common_keys:
            return 0.0

        dot = sum(v1[k] * v2[k] for k in common_keys)
        norm1 = math.sqrt(sum(v * v for v in v1.values()))
        norm2 = math.sqrt(sum(v * v for v in v2.values()))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot / (norm1 * norm2)


class HybridVectorizer:
    """Hybrid vectorizer that prefers sklearn but falls back to pure Python."""

    def __init__(self):
        self._skl_vectorizer: Optional[Any] = None
        self._py_vectorizer: Optional[LightweightTFIDF] = None
        self._use_sklearn = HAS_SKLEARN

    def fit(self, documents: List[str]) -> "HybridVectorizer":
        if self._use_sklearn:
            self._skl_vectorizer = TfidfVectorizer(
                analyzer="word",
                ngram_range=(1, 2),
                max_features=5000,
            )
            self._skl_vectorizer.fit(documents)
        else:
            self._py_vectorizer = LightweightTFIDF()
            self._py_vectorizer.fit(documents)
        return self

    def transform(self, documents: List[str]) -> Any:
        if self._use_sklearn and self._skl_vectorizer:
            return self._skl_vectorizer.transform(documents)
        elif self._py_vectorizer:
            return self._py_vectorizer.transform(documents)
        return []

    def fit_transform(self, documents: List[str]) -> Any:
        return self.fit(documents).transform(documents)

    def similarity_matrix(self, query_vec: Any, index_vecs: Any) -> List[float]:
        """Compute similarity between query and all index vectors."""
        if self._use_sklearn and HAS_NUMPY:
            sims = skl_cosine_similarity(query_vec, index_vecs)[0]
            return [float(s) for s in sims]
        else:
            if not query_vec or not index_vecs:
                return []
            q = query_vec[0] if isinstance(query_vec, list) else query_vec
            return [LightweightTFIDF.cosine_sparse(q, iv) for iv in index_vecs]
