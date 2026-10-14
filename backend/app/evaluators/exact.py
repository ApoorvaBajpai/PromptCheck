from typing import Any

from app.engine.client import BaseGeminiClient
from app.evaluators.base import BaseEvaluator, EvaluationContext, EvaluationResult


class ExactEvaluator(BaseEvaluator):
    """Evaluates whether model output matches expected text exactly."""

    evaluator_type: str = "exact"

    async def evaluate(
        self,
        actual_output: str,
        config: dict[str, Any],
        client: BaseGeminiClient | None = None,
        context: EvaluationContext | None = None,
    ) -> EvaluationResult:
        expected = config.get("expected", config.get("value", ""))
        case_sensitive = config.get("case_sensitive", True)
        strip = config.get("strip", False)

        actual_comp = actual_output.strip() if strip else actual_output
        expected_comp = str(expected).strip() if strip else str(expected)

        if not case_sensitive:
            actual_comp = actual_comp.lower()
            expected_comp = expected_comp.lower()

        passed = actual_comp == expected_comp
        score = 1.0 if passed else 0.0

        if passed:
            reason = "Output matches expected text exactly."
        else:
            reason = (
                f"Output does not match expected text. "
                f"Expected: '{str(expected)[:50]}', got: '{actual_output[:50]}'"
            )

        return EvaluationResult(
            type=self.evaluator_type,
            passed=passed,
            score=score,
            reason=reason,
            details={
                "expected": str(expected),
                "actual": actual_output,
                "case_sensitive": case_sensitive,
                "strip": strip,
            },
        )
