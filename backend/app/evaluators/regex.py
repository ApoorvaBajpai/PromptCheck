import re
from typing import Any

from app.engine.client import BaseGeminiClient
from app.evaluators.base import BaseEvaluator, EvaluationContext, EvaluationResult


class RegexEvaluator(BaseEvaluator):
    """Evaluates whether model output matches a regular expression pattern."""

    evaluator_type: str = "regex"

    async def evaluate(
        self,
        actual_output: str,
        config: dict[str, Any],
        client: BaseGeminiClient | None = None,
        context: EvaluationContext | None = None,
    ) -> EvaluationResult:
        pattern = str(config.get("pattern", config.get("value", "")))
        case_sensitive = config.get("case_sensitive", True)
        mode = config.get("mode", "search").lower()
        negate = config.get("negate", False)

        flags = 0
        if not case_sensitive:
            flags |= re.IGNORECASE
        if config.get("multiline", False):
            flags |= re.MULTILINE
        if config.get("dotall", False):
            flags |= re.DOTALL

        try:
            compiled = re.compile(pattern, flags)
        except re.error as exc:
            return EvaluationResult(
                type=self.evaluator_type,
                passed=False,
                score=0.0,
                reason=f"Invalid regular expression syntax: {exc}",
                details={"pattern": pattern, "error": str(exc)},
            )

        if mode == "fullmatch":
            match = compiled.fullmatch(actual_output)
        elif mode == "match":
            match = compiled.match(actual_output)
        else:
            match = compiled.search(actual_output)

        matched = bool(match)
        passed = not matched if negate else matched
        score = 1.0 if passed else 0.0

        if passed:
            if not negate:
                reason = f"Output matches regex pattern '{pattern}'"
            else:
                reason = f"Output correctly does not match forbidden regex pattern '{pattern}'"
        else:
            if not negate:
                reason = f"Output does not match required regex pattern '{pattern}'"
            else:
                reason = f"Output unexpectedly matches forbidden regex pattern '{pattern}'"

        details: dict[str, Any] = {
            "pattern": pattern,
            "mode": mode,
            "case_sensitive": case_sensitive,
            "negate": negate,
            "matched_text": match.group(0) if match else None,
            "span": match.span() if match else None,
        }

        return EvaluationResult(
            type=self.evaluator_type,
            passed=passed,
            score=score,
            reason=reason,
            details=details,
        )
