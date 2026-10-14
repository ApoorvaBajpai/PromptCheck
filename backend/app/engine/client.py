import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx


class GeminiError(Exception):
    """Base error for Gemini API client interactions."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code


class GeminiRateLimitError(GeminiError):
    """Raised when Gemini returns HTTP 429 (Too Many Requests / Quota Exceeded)."""

    def __init__(self, message: str = "Gemini API rate limit exceeded (HTTP 429)"):
        super().__init__(message, status_code=429)


class GeminiServerError(GeminiError):
    """Raised when Gemini returns a 5xx server error."""

    def __init__(self, message: str = "Gemini API server error", status_code: int = 500):
        super().__init__(message, status_code=status_code)


class GeminiAuthError(GeminiError):
    """Raised when Gemini rejects the API key (HTTP 400 or 403)."""

    def __init__(self, message: str = "Invalid or missing Gemini API key"):
        super().__init__(message, status_code=403)


@dataclass
class GeminiResponse:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0


class BaseGeminiClient(ABC):
    """Abstract interface for Gemini model clients."""

    @abstractmethod
    async def generate_content(
        self,
        prompt: str,
        model: str = "gemini-1.5-flash",
    ) -> GeminiResponse:
        """Generate content from the model."""
        pass


class GeminiClient(BaseGeminiClient):
    """Production client calling Google Gemini REST API using httpx."""

    def __init__(self, api_key: str, timeout: float = 30.0):
        self.api_key = api_key
        self.timeout = timeout
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    async def generate_content(
        self,
        prompt: str,
        model: str = "gemini-1.5-flash",
    ) -> GeminiResponse:
        if not self.api_key or self.api_key.strip() == "":
            raise GeminiAuthError("API key cannot be empty")

        url = f"{self.base_url}/{model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}],
                }
            ]
        }

        start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload)
            except httpx.TimeoutException as exc:
                raise GeminiServerError("Gemini API request timed out", status_code=504) from exc
            except httpx.RequestError as exc:
                raise GeminiServerError(
                    f"Network error connecting to Gemini: {exc}", status_code=502
                ) from exc

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        if response.status_code == 429:
            raise GeminiRateLimitError(response.text)
        elif response.status_code in (400, 401, 403):
            # Check if error is related to invalid API key
            raise GeminiAuthError(f"Authentication failed: {response.text}")
        elif response.status_code >= 500:
            raise GeminiServerError(response.text, status_code=response.status_code)
        elif response.status_code != 200:
            raise GeminiError(
                f"Unexpected response ({response.status_code}): {response.text}",
                status_code=response.status_code,
            )

        data = response.json()
        try:
            candidates = data.get("candidates", [])
            if candidates and "content" in candidates[0]:
                parts = candidates[0]["content"].get("parts", [])
                text = "".join([p.get("text", "") for p in parts])
            else:
                text = ""
        except Exception:
            text = ""

        usage = data.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", len(prompt.split()) * 4 // 3)
        completion_tokens = usage.get("candidatesTokenCount", len(text.split()) * 4 // 3)
        total_tokens = usage.get("totalTokenCount", prompt_tokens + completion_tokens)

        return GeminiResponse(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=round(latency_ms, 2),
        )


class FakeGeminiClient(BaseGeminiClient):
    """Programmable mock Gemini client for deterministic unit & integration tests."""

    def __init__(
        self,
        default_response: str = "Fake model generated output.",
        simulated_latency_ms: float = 5.0,
    ):
        self.default_response = default_response
        self.simulated_latency_ms = simulated_latency_ms
        self.prompt_responses: dict[str, str] = {}
        self.calls: list[dict[str, Any]] = []

        # Simulated failure counters
        self.fail_429_count = 0
        self.fail_500_count = 0
        self.is_invalid_api_key = False

    def set_response_for_prompt(self, prompt_substring: str, response: str) -> None:
        """Map a substring to a specific response string."""
        self.prompt_responses[prompt_substring] = response

    def set_fail_with_429(self, count: int = 1) -> None:
        """Configure client to raise 429 for the next `count` calls."""
        self.fail_429_count = count

    def set_fail_with_500(self, count: int = 1) -> None:
        """Configure client to raise 500 for the next `count` calls."""
        self.fail_500_count = count

    def set_invalid_api_key(self, is_invalid: bool = True) -> None:
        """Simulate invalid API key rejection."""
        self.is_invalid_api_key = is_invalid

    async def generate_content(
        self,
        prompt: str,
        model: str = "gemini-1.5-flash",
    ) -> GeminiResponse:
        self.calls.append({"prompt": prompt, "model": model, "timestamp": time.time()})

        if self.is_invalid_api_key:
            raise GeminiAuthError("Invalid Gemini API key provided")

        if self.fail_429_count > 0:
            self.fail_429_count -= 1
            raise GeminiRateLimitError("Simulated 429 Too Many Requests")

        if self.fail_500_count > 0:
            self.fail_500_count -= 1
            raise GeminiServerError("Simulated 500 Internal Server Error", status_code=500)

        # Matched response (sort keys descending by length so longer substrings match first)
        text = self.default_response
        sorted_pairs = sorted(
            self.prompt_responses.items(), key=lambda item: len(item[0]), reverse=True
        )
        for sub, resp in sorted_pairs:
            if sub in prompt:
                text = resp
                break

        # Simulate tokens based on content length
        prompt_tokens = max(1, len(prompt.split()) * 2)
        completion_tokens = max(1, len(text.split()) * 2)
        total_tokens = prompt_tokens + completion_tokens

        return GeminiResponse(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=self.simulated_latency_ms,
        )
