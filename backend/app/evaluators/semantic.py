import asyncio
import math
from typing import Any

from app.engine.client import BaseGeminiClient
from app.evaluators.base import BaseEvaluator, EvaluationContext, EvaluationResult


def compute_cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute normalized cosine similarity between two numerical vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    sim = dot_product / (norm_a * norm_b)
    # Clamp in [0.0, 1.0] to account for floating-point inaccuracies
    return max(0.0, min(1.0, sim))


class ReferenceEmbeddingCache:
    """Thread-safe and async-safe in-memory cache for reference text embeddings."""

    def __init__(self):
        self._cache: dict[tuple[str, str], list[float]] = {}
        self._lock = asyncio.Lock()

    async def get_or_compute(
        self,
        text: str,
        model: str,
        client: BaseGeminiClient,
    ) -> tuple[list[float], bool]:
        """Retrieve cached embedding or compute and cache a new embedding vector."""
        cache_key = (model, text)
        async with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key], True

        # Compute embedding using Gemini client
        embedding = await client.embed_content(text, model=model)

        async with self._lock:
            self._cache[cache_key] = embedding

        return embedding, False

    async def clear(self) -> None:
        """Clear cached reference embeddings."""
        async with self._lock:
            self._cache.clear()


# Global reference embedding cache instance
reference_embedding_cache = ReferenceEmbeddingCache()


class SemanticEvaluator(BaseEvaluator):
    """
    Evaluates semantic similarity between model output and reference text
    using Gemini embeddings and cosine similarity.
    """

    evaluator_type: str = "semantic"

    async def evaluate(
        self,
        actual_output: str,
        config: dict[str, Any],
        client: BaseGeminiClient | None = None,
        context: EvaluationContext | None = None,
    ) -> EvaluationResult:
        reference = str(
            config.get("reference", config.get("reference_text", config.get("expected", config.get("target", ""))))
        )
        threshold = float(config.get("threshold", 0.8))
        model = str(config.get("model", "gemini-embedding-001"))

        if not client:
            return EvaluationResult(
                type=self.evaluator_type,
                passed=False,
                score=0.0,
                reason="GeminiClient not provided for semantic similarity evaluation.",
                details={"error": "Missing client"},
            )

        if not reference.strip():
            return EvaluationResult(
                type=self.evaluator_type,
                passed=False,
                score=0.0,
                reason="Semantic evaluator requires a non-empty reference text.",
                details={"reference": reference},
            )

        try:
            # 1. Fetch or compute reference embedding (cached)
            ref_vec, was_cached = await reference_embedding_cache.get_or_compute(
                text=reference,
                model=model,
                client=client,
            )

            # 2. Compute actual output embedding
            actual_vec = await client.embed_content(actual_output, model=model)

            # 3. Compute cosine similarity
            similarity = round(compute_cosine_similarity(actual_vec, ref_vec), 4)

            passed = similarity >= threshold
            score = similarity

            if passed:
                reason = (
                    f"Semantic similarity ({similarity:.4f}) meets or exceeds threshold ({threshold})."
                )
            else:
                reason = (
                    f"Semantic similarity ({similarity:.4f}) is below required threshold ({threshold})."
                )

            return EvaluationResult(
                type=self.evaluator_type,
                passed=passed,
                score=score,
                reason=reason,
                details={
                    "similarity": similarity,
                    "threshold": threshold,
                    "reference": reference[:100],
                    "model": model,
                    "cached_reference": was_cached,
                },
            )
        except Exception as exc:
            return EvaluationResult(
                type=self.evaluator_type,
                passed=False,
                score=0.0,
                reason=f"Semantic similarity evaluation failed: {exc}",
                details={"error": str(exc), "reference": reference[:100], "model": model},
            )
