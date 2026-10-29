"""Local-first embedding backends for the RAG vector store.

Resolution order is explicit via settings:
1. ``local_hash`` — deterministic, zero-download default (always available).
2. ``nomic_ollama`` — ``nomic-embed-text`` via the local Ollama daemon.
3. ``fastembed`` — ONNX FastEmbed if the optional package is installed.

Cloud embedding APIs are intentionally omitted so the knowledge base can run
offline. Heavy model downloads are never triggered unless the operator
explicitly selects ``fastembed`` or has already pulled ``nomic-embed-text``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import urllib.error
import urllib.request
from typing import Any, Literal

logger = logging.getLogger(__name__)

EmbeddingProviderType = Literal["local_hash", "nomic_ollama", "fastembed"]

DEFAULT_HASH_DIM = 64
DEFAULT_NOMIC_MODEL = "nomic-embed-text"
DEFAULT_FASTEMBED_MODEL = "BAAI/bge-small-en-v1.5"


class DefaultLocalEmbeddingFunction:
    """Deterministic 64-dim L2-normalized bag-of-words hash embedding.

    Uses BLAKE2b rather than Python's salted ``hash()`` so persisted ChromaDB
    collections remain queryable across process restarts.
    """

    supported_spaces = ["cosine", "l2", "ip"]

    def __init__(self, dim: int = DEFAULT_HASH_DIM) -> None:
        self.dim = dim

    def name(self) -> str:
        return "default_local_hash"

    def is_legacy(self) -> bool:
        return False

    def embed_with_retries(self, input: list[str], **kwargs: Any) -> list[list[float]]:
        return self(input)

    def embed_query(self, input: str | list[str]) -> list[float] | list[list[float]]:
        if isinstance(input, str):
            return self([input])[0]
        return self(input)

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        return self(input)

    def __call__(self, input: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in input:
            vec = [0.0] * self.dim
            words = re.findall(r"\b[a-zA-Z0-9]{2,}\b", text.lower())
            for word in words:
                digest = hashlib.blake2b(word.encode("utf-8"), digest_size=8).digest()
                idx = int.from_bytes(digest, "little") % self.dim
                vec[idx] += 1.0
            norm = math.sqrt(sum(value * value for value in vec))
            if norm > 0.0:
                vec = [value / norm for value in vec]
            embeddings.append(vec)
        return embeddings


class OllamaNomicEmbeddingFunction:
    """Embeds documents through a local Ollama ``nomic-embed-text`` model."""

    supported_spaces = ["cosine", "l2", "ip"]

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = DEFAULT_NOMIC_MODEL,
        timeout_seconds: float = 8.0,
    ) -> None:
        stripped = base_url.rstrip("/")
        if stripped.endswith("/v1"):
            stripped = stripped[:-3]
        self.base_url = stripped
        self.model = model
        self.timeout_seconds = timeout_seconds

    def name(self) -> str:
        return f"ollama_{self.model}"

    def is_legacy(self) -> bool:
        return False

    def embed_with_retries(self, input: list[str], **kwargs: Any) -> list[list[float]]:
        return self(input)

    def embed_query(self, input: str | list[str]) -> list[float] | list[list[float]]:
        if isinstance(input, str):
            return self([input])[0]
        return self(input)

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        return self(input)

    def __call__(self, input: list[str]) -> list[list[float]]:
        payload = json.dumps({"model": self.model, "input": input}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            raise RuntimeError(f"Ollama embedding request failed: {exc}") from exc

        embeddings = body.get("embeddings")
        if not embeddings:
            raise RuntimeError("Ollama embedding response did not include embeddings.")
        return embeddings


class FastEmbedEmbeddingFunction:
    """Optional FastEmbed ONNX backend (requires the ``fastembed`` package)."""

    supported_spaces = ["cosine", "l2", "ip"]

    def __init__(self, model_name: str = DEFAULT_FASTEMBED_MODEL) -> None:
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:
            raise RuntimeError("fastembed is not installed.") from exc
        self.model_name = model_name
        self._model = TextEmbedding(model_name=model_name)

    def name(self) -> str:
        return f"fastembed_{self.model_name}"

    def is_legacy(self) -> bool:
        return False

    def embed_with_retries(self, input: list[str], **kwargs: Any) -> list[list[float]]:
        return self(input)

    def embed_query(self, input: str | list[str]) -> list[float] | list[list[float]]:
        if isinstance(input, str):
            return self([input])[0]
        return self(input)

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        return self(input)

    def __call__(self, input: list[str]) -> list[list[float]]:
        return [list(vector) for vector in self._model.embed(input)]


def get_embedding_function(
    provider: EmbeddingProviderType = "local_hash",
    ollama_base_url: str = "http://localhost:11434",
    embedding_model: str = DEFAULT_NOMIC_MODEL,
) -> Any:
    """Returns an embedding function, falling back to local hash on failure."""
    selected = (provider or "local_hash").lower().strip()

    if selected == "nomic_ollama":
        try:
            function = OllamaNomicEmbeddingFunction(
                base_url=ollama_base_url,
                model=embedding_model or DEFAULT_NOMIC_MODEL,
            )
            logger.info("Using Ollama embeddings: model=%s", function.model)
            return function
        except Exception as exc:
            logger.warning("nomic_ollama embeddings unavailable (%s); using local_hash.", exc)

    elif selected == "fastembed":
        try:
            function = FastEmbedEmbeddingFunction(
                model_name=embedding_model or DEFAULT_FASTEMBED_MODEL,
            )
            logger.info("Using FastEmbed embeddings: model=%s", function.model_name)
            return function
        except Exception as exc:
            logger.warning("fastembed embeddings unavailable (%s); using local_hash.", exc)

    return DefaultLocalEmbeddingFunction()
