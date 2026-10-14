from typing import Any

from app.engine.client import BaseGeminiClient
from app.evaluators.base import BaseEvaluator, EvaluationContext, EvaluationResult
from app.evaluators.contains import ContainsEvaluator
from app.evaluators.exact import ExactEvaluator
from app.evaluators.json_schema import JsonSchemaEvaluator
from app.evaluators.length import LengthEvaluator
from app.evaluators.llm_judge import LLMJudgeEvaluator
from app.evaluators.regex import RegexEvaluator
from app.evaluators.semantic import SemanticEvaluator

_EXACT = ExactEvaluator()
_CONTAINS = ContainsEvaluator()
_REGEX = RegexEvaluator()
_JSON_SCHEMA = JsonSchemaEvaluator()
_LENGTH = LengthEvaluator()
_SEMANTIC = SemanticEvaluator()
_LLM_JUDGE = LLMJudgeEvaluator()

EVALUATOR_REGISTRY: dict[str, BaseEvaluator] = {
    "exact": _EXACT,
    "contains": _CONTAINS,
    "regex": _REGEX,
    "json_schema": _JSON_SCHEMA,
    "length": _LENGTH,
    "semantic": _SEMANTIC,
    "llm_judge": _LLM_JUDGE,
}

# Alias mapping for backward compatibility and alternate user naming
_ALIASES: dict[str, str] = {
    "equals": "exact",
    "equal": "exact",
    "contain": "contains",
    "not_contains": "contains",
    "does_not_contain": "contains",
    "not_contain": "contains",
    "matches": "regex",
    "match": "regex",
    "schema": "json_schema",
    "json": "json_schema",
    "max_length": "length",
    "min_length": "length",
    "exact_length": "length",
    "embedding": "semantic",
    "semantic_similarity": "semantic",
    "similarity": "semantic",
    "judge": "llm_judge",
    "llm": "llm_judge",
}


def get_evaluator(eval_type: str) -> BaseEvaluator | None:
    """Retrieve an evaluator instance by its canonical type name or alias."""
    norm = eval_type.strip().lower()
    canonical = _ALIASES.get(norm, norm)
    return EVALUATOR_REGISTRY.get(canonical)


async def evaluate_single(
    actual_output: str,
    assertion: dict[str, Any],
    client: BaseGeminiClient | None = None,
    context: EvaluationContext | None = None,
) -> EvaluationResult:
    """Evaluate a single assertion against output using the evaluator framework."""
    raw_type = str(assertion.get("type", "contains")).strip().lower()

    # Pre-configure negation for legacy not_contains aliases
    config = dict(assertion)
    if raw_type in ("not_contains", "does_not_contain", "not_contain"):
        config["negate"] = True
    elif raw_type in ("max_length", "max_len"):
        config["max_length"] = config.get("value")
    elif raw_type in ("min_length", "min_len"):
        config["min_length"] = config.get("value")

    evaluator = get_evaluator(raw_type)
    if not evaluator:
        return EvaluationResult(
            type=raw_type,
            passed=False,
            score=0.0,
            reason=f"Unknown or unsupported evaluator type: '{raw_type}'.",
            details={"raw_assertion": assertion},
        )

    try:
        return await evaluator.evaluate(
            actual_output=actual_output,
            config=config,
            client=client,
            context=context,
        )
    except Exception as exc:
        # Guarantee that evaluator failures produce explainable results rather than crashing
        return EvaluationResult(
            type=raw_type,
            passed=False,
            score=0.0,
            reason=f"Evaluator '{raw_type}' encountered an unexpected internal error: {exc}",
            details={"error": str(exc), "assertion": assertion},
        )


async def evaluate_all(
    actual_output: str,
    assertions: list[dict[str, Any]],
    client: BaseGeminiClient | None = None,
    context: EvaluationContext | None = None,
) -> tuple[bool, list[dict[str, Any]]]:
    """
    Evaluate all assertions sequentially or concurrently.
    Returns (all_passed: bool, list_of_result_dicts).
    """
    if not assertions:
        return True, []

    results: list[dict[str, Any]] = []
    all_passed = True

    for a in assertions:
        res = await evaluate_single(
            actual_output=actual_output,
            assertion=a,
            client=client,
            context=context,
        )
        if not res.passed:
            all_passed = False
        results.append(res.model_dump())

    return all_passed, results
