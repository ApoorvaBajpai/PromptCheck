import json
from typing import Any

import jsonschema

from app.engine.client import BaseGeminiClient
from app.evaluators.base import BaseEvaluator, EvaluationContext, EvaluationResult


class JsonSchemaEvaluator(BaseEvaluator):
    """Evaluates whether model output is valid JSON and conforms to a given JSON Schema."""

    evaluator_type: str = "json_schema"

    async def evaluate(
        self,
        actual_output: str,
        config: dict[str, Any],
        client: BaseGeminiClient | None = None,
        context: EvaluationContext | None = None,
    ) -> EvaluationResult:
        schema = config.get("schema", config.get("value", {}))
        if isinstance(schema, str):
            try:
                schema = json.loads(schema)
            except Exception as exc:
                return EvaluationResult(
                    type=self.evaluator_type,
                    passed=False,
                    score=0.0,
                    reason=f"Invalid JSON schema definition string: {exc}",
                    details={"error": str(exc), "schema": str(schema)},
                )

        # 1. Parse actual output as JSON
        # Clean potential markdown code blocks first
        cleaned_output = actual_output.strip()
        if cleaned_output.startswith("```"):
            lines = cleaned_output.splitlines()
            if len(lines) >= 2 and lines[0].startswith("```"):
                cleaned_output = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            parsed_json = json.loads(cleaned_output)
        except json.JSONDecodeError as exc:
            return EvaluationResult(
                type=self.evaluator_type,
                passed=False,
                score=0.0,
                reason=f"Output is not valid JSON: {exc.msg} (line {exc.lineno}, col {exc.colno})",
                details={
                    "error": str(exc),
                    "lineno": exc.lineno,
                    "colno": exc.colno,
                    "raw_output": actual_output[:200],
                },
            )

        # 2. Validate against JSON Schema
        try:
            jsonschema.validate(instance=parsed_json, schema=schema)
        except jsonschema.SchemaError as exc:
            return EvaluationResult(
                type=self.evaluator_type,
                passed=False,
                score=0.0,
                reason=f"Invalid JSON schema definition: {exc.message}",
                details={"error": exc.message, "validator": exc.validator},
            )
        except jsonschema.ValidationError as exc:
            path_str = " -> ".join([str(p) for p in exc.path]) or "root"
            return EvaluationResult(
                type=self.evaluator_type,
                passed=False,
                score=0.0,
                reason=f"JSON schema validation failed at '{path_str}': {exc.message}",
                details={
                    "error": exc.message,
                    "path": list(exc.path),
                    "validator": exc.validator,
                    "validator_value": str(exc.validator_value),
                },
            )

        return EvaluationResult(
            type=self.evaluator_type,
            passed=True,
            score=1.0,
            reason="Output is valid JSON and conforms to the specified schema.",
            details={"schema": schema},
        )
