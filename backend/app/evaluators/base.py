from abc import ABC, abstractmethod
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.engine.client import BaseGeminiClient


class EvaluationResult(BaseModel):
    """
    Standard evaluation output returned by every PromptCheck evaluator.
    Required fields: type, passed, score, reason, details.
    """

    type: str
    passed: bool
    score: float
    reason: str
    details: dict[str, Any] = Field(default_factory=dict)
    status: str = "evaluated"
    is_evaluator_error: bool = False


class EvaluationContext(BaseModel):
    """Optional contextual data provided to evaluators during run execution."""

    rendered_prompt: str | None = None
    test_inputs: dict[str, Any] = Field(default_factory=dict)
    test_case_name: str | None = None


class Evaluator(Protocol):
    """Protocol defining the standard evaluator interface."""

    type: str

    async def evaluate(
        self,
        actual_output: str,
        config: dict[str, Any],
        client: BaseGeminiClient | None = None,
        context: EvaluationContext | None = None,
    ) -> EvaluationResult:
        ...


class BaseEvaluator(ABC):
    """Abstract base class for PromptCheck evaluators."""

    evaluator_type: str = ""

    @abstractmethod
    async def evaluate(
        self,
        actual_output: str,
        config: dict[str, Any],
        client: BaseGeminiClient | None = None,
        context: EvaluationContext | None = None,
    ) -> EvaluationResult:
        """
        Evaluate actual model output against assertion configuration.
        Must never raise an unhandled exception that crashes the run.
        """
        pass
