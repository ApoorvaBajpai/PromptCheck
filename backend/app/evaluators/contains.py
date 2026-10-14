from typing import Any

from app.engine.client import BaseGeminiClient
from app.evaluators.base import BaseEvaluator, EvaluationContext, EvaluationResult


class ContainsEvaluator(BaseEvaluator):
    """Evaluates whether model output contains expected substring(s)."""

    evaluator_type: str = "contains"

    async def evaluate(
        self,
        actual_output: str,
        config: dict[str, Any],
        client: BaseGeminiClient | None = None,
        context: EvaluationContext | None = None,
    ) -> EvaluationResult:
        raw_val = config.get("value", config.get("expected", config.get("substring", config.get("substrings", []))))
        if isinstance(raw_val, list):
            substrings = [str(s) for s in raw_val]
        else:
            substrings = [str(raw_val)] if raw_val is not None else []

        case_sensitive = config.get("case_sensitive", True)
        mode = config.get("mode", "all").lower()
        negate = config.get("negate", False)

        target_text = actual_output if case_sensitive else actual_output.lower()

        found_list: list[str] = []
        missing_list: list[str] = []

        for sub in substrings:
            query = sub if case_sensitive else sub.lower()
            if query in target_text:
                found_list.append(sub)
            else:
                missing_list.append(sub)

        total = len(substrings) or 1
        if not negate:
            if mode == "any":
                passed = len(found_list) > 0
                score = 1.0 if passed else 0.0
            else:
                passed = len(found_list) == len(substrings)
                score = round(len(found_list) / total, 3)

            if passed:
                reason = f"Output successfully contains required substring(s): {found_list}"
            else:
                reason = f"Output missing required substring(s): {missing_list}"
        else:
            # Negated check (not_contains)
            passed = len(found_list) == 0
            score = 1.0 if passed else 0.0
            if passed:
                reason = f"Output successfully does not contain forbidden substring(s): {substrings}"
            else:
                reason = f"Output contains forbidden substring(s): {found_list}"

        return EvaluationResult(
            type=self.evaluator_type,
            passed=passed,
            score=score,
            reason=reason,
            details={
                "substrings": substrings,
                "found": found_list,
                "missing": missing_list,
                "mode": mode,
                "case_sensitive": case_sensitive,
                "negate": negate,
            },
        )
