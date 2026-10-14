from typing import Any

from app.engine.client import BaseGeminiClient
from app.evaluators.base import BaseEvaluator, EvaluationContext, EvaluationResult


class LengthEvaluator(BaseEvaluator):
    """Evaluates whether model output satisfies character or word length constraints."""

    evaluator_type: str = "length"

    async def evaluate(
        self,
        actual_output: str,
        config: dict[str, Any],
        client: BaseGeminiClient | None = None,
        context: EvaluationContext | None = None,
    ) -> EvaluationResult:
        unit = config.get("unit", "characters").lower()
        if unit in ("word", "words"):
            actual_len = len(actual_output.split())
            unit_label = "words"
        else:
            actual_len = len(actual_output)
            unit_label = "characters"

        min_len = config.get("min_length", config.get("min"))
        max_len = config.get("max_length", config.get("max"))
        exact_len = config.get("exact_length", config.get("exact"))

        passed = True
        violations: list[str] = []

        if exact_len is not None:
            exact_val = int(exact_len)
            if actual_len != exact_val:
                passed = False
                violations.append(f"expected exactly {exact_val} {unit_label}")

        if min_len is not None:
            min_val = int(min_len)
            if actual_len < min_val:
                passed = False
                violations.append(f"less than minimum {min_val} {unit_label}")

        if max_len is not None:
            max_val = int(max_len)
            if actual_len > max_val:
                passed = False
                violations.append(f"exceeds maximum {max_val} {unit_label}")

        score = 1.0 if passed else 0.0

        if passed:
            reason = f"Output length ({actual_len} {unit_label}) satisfies all length constraints."
        else:
            reason = (
                f"Output length ({actual_len} {unit_label}) failed constraint(s): "
                f"{', '.join(violations)}."
            )

        return EvaluationResult(
            type=self.evaluator_type,
            passed=passed,
            score=score,
            reason=reason,
            details={
                "actual_length": actual_len,
                "unit": unit_label,
                "min_length": min_len,
                "max_length": max_len,
                "exact_length": exact_len,
            },
        )
