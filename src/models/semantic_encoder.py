import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from dataclasses import dataclass, field

logger = logging.getLogger("uvmgen.ml.semantic")


@dataclass
class SemanticEmbedding:
    vector: np.ndarray
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding_type: str = "code"

    @property
    def dim(self) -> int:
        return len(self.vector)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vector": self.vector.tolist(),
            "text": self.text,
            "metadata": self.metadata,
            "embedding_type": self.embedding_type,
            "dim": self.dim,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SemanticEmbedding":
        return cls(
            vector=np.array(d["vector"], dtype=np.float32),
            text=d["text"],
            metadata=d.get("metadata", {}),
            embedding_type=d.get("embedding_type", "code"),
        )


class SemanticCodeEncoder:
    _instance: Optional["SemanticCodeEncoder"] = None
    _model = None
    _tokenizer = None
    _model_name: str = "microsoft/codebert-base"
    _device: str = "cpu"
    _initialized: bool = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, model_name: Optional[str] = None, device: Optional[str] = None):
        if self._initialized:
            return

        if model_name:
            self._model_name = model_name
        if device:
            self._device = device

        self._initialized = False
        self._model = None
        self._tokenizer = None

    def _load_model(self):
        if self._initialized and self._model is not None:
            return

        try:
            import torch
            from transformers import AutoTokenizer, AutoModel

            if self._device == "auto":
                self._device = "cuda" if torch.cuda.is_available() else "cpu"

            logger.info("Loading semantic encoder: %s on %s", self._model_name, self._device)

            self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
            self._model = AutoModel.from_pretrained(self._model_name)
            self._model.to(self._device)
            self._model.eval()

            self._initialized = True
            logger.info("Semantic encoder loaded successfully")

        except ImportError as e:
            logger.warning(
                "Could not load semantic encoder (missing dependencies: %s). "
                "Using fallback TF-IDF-based similarity.",
                e,
            )
            self._initialized = False
            self._model = None
            self._tokenizer = None
        except Exception as e:
            logger.warning(
                "Could not load semantic encoder (%s). Using fallback similarity.",
                e,
            )
            self._initialized = False
            self._model = None
            self._tokenizer = None

    def is_available(self) -> bool:
        self._load_model()
        return self._initialized and self._model is not None

    def encode(
        self,
        text: str,
        embedding_type: str = "code",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SemanticEmbedding:
        self._load_model()

        if not self.is_available():
            return self._fallback_encode(text, embedding_type, metadata)

        try:
            import torch

            inputs = self._tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True,
            )
            inputs = {k: v.to(self._device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self._model(**inputs)
                embeddings = outputs.last_hidden_state[:, 0, :]
                embeddings = embeddings.cpu().numpy().squeeze()

            embeddings = embeddings / (np.linalg.norm(embeddings) + 1e-8)

            return SemanticEmbedding(
                vector=embeddings.astype(np.float32),
                text=text,
                metadata=metadata or {},
                embedding_type=embedding_type,
            )

        except Exception as e:
            logger.warning("Error encoding with neural model: %s. Using fallback.", e)
            return self._fallback_encode(text, embedding_type, metadata)

    def encode_batch(
        self,
        texts: List[str],
        embedding_type: str = "code",
        metadata_list: Optional[List[Dict[str, Any]]] = None,
    ) -> List[SemanticEmbedding]:
        self._load_model()

        if not self.is_available():
            return [
                self._fallback_encode(text, embedding_type, metadata_list[i] if metadata_list else None)
                for i, text in enumerate(texts)
            ]

        try:
            import torch

            inputs = self._tokenizer(
                texts,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True,
            )
            inputs = {k: v.to(self._device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self._model(**inputs)
                embeddings = outputs.last_hidden_state[:, 0, :]
                embeddings = embeddings.cpu().numpy()

            norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-8
            embeddings = embeddings / norms

            results = []
            for i, emb in enumerate(embeddings):
                results.append(
                    SemanticEmbedding(
                        vector=emb.astype(np.float32),
                        text=texts[i],
                        metadata=metadata_list[i] if metadata_list else {},
                        embedding_type=embedding_type,
                    )
                )
            return results

        except Exception as e:
            logger.warning("Error batch encoding: %s. Using fallback.", e)
            return [
                self._fallback_encode(text, embedding_type, metadata_list[i] if metadata_list else None)
                for i, text in enumerate(texts)
            ]

    def _fallback_encode(
        self,
        text: str,
        embedding_type: str = "code",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SemanticEmbedding:
        words = text.lower().split()
        vocab = sorted(set(words))
        vec = np.zeros(len(vocab), dtype=np.float32)

        for w in words:
            if w in vocab:
                vec[vocab.index(w)] += 1

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm

        pad_size = 128 - len(vec)
        if pad_size > 0:
            vec = np.pad(vec, (0, pad_size), mode="constant")
        elif pad_size < 0:
            vec = vec[:128]

        return SemanticEmbedding(
            vector=vec.astype(np.float32),
            text=text,
            metadata=metadata or {},
            embedding_type=embedding_type,
        )

    def similarity(self, emb1: SemanticEmbedding, emb2: SemanticEmbedding) -> float:
        if len(emb1.vector) != len(emb2.vector):
            min_len = min(len(emb1.vector), len(emb2.vector))
            v1 = emb1.vector[:min_len]
            v2 = emb2.vector[:min_len]
        else:
            v1 = emb1.vector
            v2 = emb2.vector

        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 < 1e-8 or norm2 < 1e-8:
            return 0.0

        return float(np.dot(v1, v2) / (norm1 * norm2))

    def batch_similarity(
        self,
        query_emb: SemanticEmbedding,
        embeddings: List[SemanticEmbedding],
    ) -> List[Tuple[int, float]]:
        if not embeddings:
            return []

        q_vec = query_emb.vector
        q_norm = np.linalg.norm(q_vec)

        if q_norm < 1e-8:
            return [(i, 0.0) for i in range(len(embeddings))]

        results = []
        for i, emb in enumerate(embeddings):
            e_vec = emb.vector

            if len(e_vec) != len(q_vec):
                min_len = min(len(q_vec), len(e_vec))
                qv = q_vec[:min_len]
                ev = e_vec[:min_len]
            else:
                qv = q_vec
                ev = e_vec

            e_norm = np.linalg.norm(ev)
            if e_norm < 1e-8:
                results.append((i, 0.0))
                continue

            sim = float(np.dot(qv, ev) / (q_norm * e_norm))
            results.append((i, sim))

        return results


def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)

    if norm1 < 1e-8 or norm2 < 1e-8:
        return 0.0

    return float(np.dot(v1, v2) / (norm1 * norm2))
