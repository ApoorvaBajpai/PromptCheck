import math
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx


def redact_api_key(text: str, api_key: str | None = None) -> str:
    """Sanitize and redact API keys from strings, exception messages, and URLs."""
    if not text:
        return ""
    clean = text
    if api_key and api_key.strip():
        clean = clean.replace(api_key, "[REDACTED_API_KEY]")
    clean = re.sub(r"key=[A-Za-z0-9_\-]+", "key=[REDACTED]", clean)
    clean = re.sub(r"AIza[0-9A-Za-z-_]{35}", "[REDACTED_API_KEY]", clean)
    return clean


class GeminiError(Exception):
    """Base error for Gemini API client interactions."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(redact_api_key(message))
        self.status_code = status_code


class GeminiRateLimitError(GeminiError):
    """Raised when Gemini returns HTTP 429 (Too Many Requests / Quota Exceeded)."""

    def __init__(self, message: str = "Gemini API rate limit exceeded (HTTP 429)"):
        super().__init__(message, status_code=429)


class GeminiServerError(GeminiError):
    """Raised when Gemini returns a 5xx server error or network failure."""

    def __init__(self, message: str = "Gemini API server error", status_code: int = 500):
        super().__init__(message, status_code=status_code)


class GeminiAuthError(GeminiError):
    """Raised when Gemini rejects the API key (HTTP 400 or 403 with invalid credentials)."""

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
        model: str = "gemini-2.5-flash",
        temperature: float = 1.0,
        system_instruction: str | None = None,
        top_p: float | None = None,
        max_output_tokens: int | None = None,
        response_mime_type: str | None = None,
    ) -> GeminiResponse:
        """Generate content from the model."""
        pass

    @abstractmethod
    async def embed_content(
        self,
        text: str,
        model: str = "gemini-embedding-001",
    ) -> list[float]:
        """Generate text embedding vector."""
        pass

    async def validate_key(self) -> bool:
        """Validate key against the service."""
        return True


class GeminiClient(BaseGeminiClient):
    """Production client calling Google Gemini REST API using httpx."""

    def __init__(self, api_key: str, timeout: float = 30.0):
        self.api_key = api_key
        self.timeout = timeout
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    async def generate_content(
        self,
        prompt: str,
        model: str = "gemini-2.5-flash",
        temperature: float = 1.0,
        system_instruction: str | None = None,
        top_p: float | None = None,
        max_output_tokens: int | None = None,
        response_mime_type: str | None = None,
    ) -> GeminiResponse:
        if not self.api_key or self.api_key.strip() == "":
            raise GeminiAuthError("API key cannot be empty")

        target_model = (
            "gemini-2.5-flash" if model in ("gemini-1.5-flash", "gemini-flash") else model
        )
        url = f"{self.base_url}/{target_model}:generateContent?key={self.api_key}"

        payload: dict[str, Any] = {
            "contents": [
                {
                    "parts": [{"text": prompt}],
                }
            ]
        }

        if system_instruction and system_instruction.strip():
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction.strip()}],
            }

        generation_config: dict[str, Any] = {}
        if temperature != 1.0:
            generation_config["temperature"] = temperature
        if top_p is not None:
            generation_config["topP"] = top_p
        if max_output_tokens is not None:
            generation_config["maxOutputTokens"] = max_output_tokens
        if response_mime_type:
            generation_config["responseMimeType"] = response_mime_type

        if generation_config:
            payload["generationConfig"] = generation_config

        start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload)
            except httpx.TimeoutException as exc:
                raise GeminiServerError("Gemini API request timed out", status_code=504) from exc
            except httpx.RequestError as exc:
                clean_err = redact_api_key(str(exc), self.api_key)
                raise GeminiServerError(
                    f"Network error connecting to Gemini: {clean_err}", status_code=502
                ) from exc

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        clean_resp = redact_api_key(response.text, self.api_key)

        if response.status_code == 429:
            raise GeminiRateLimitError(clean_resp)
        elif response.status_code in (400, 401, 403):
            # Check if this 400 is actually quota exhaustion or invalid argument vs bad key
            if "RESOURCE_EXHAUSTED" in clean_resp or "quota" in clean_resp.lower():
                raise GeminiRateLimitError(clean_resp)
            raise GeminiAuthError(f"Authentication failed: {clean_resp}")
        elif response.status_code >= 500:
            raise GeminiServerError(clean_resp, status_code=response.status_code)
        elif response.status_code != 200:
            raise GeminiError(
                f"Unexpected response ({response.status_code}): {clean_resp}",
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

    async def validate_key(self) -> bool:
        """
        Validate this API key with a minimal probe request.
        Raises GeminiAuthError, GeminiRateLimitError, or GeminiServerError accordingly.
        """
        # Minimal probe to gemini-2.5-flash
        url = f"{self.base_url}/gemini-2.5-flash:generateContent?key={self.api_key}"
        payload = {"contents": [{"parts": [{"text": "ping"}]}], "generationConfig": {"maxOutputTokens": 1}}
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url, json=payload)
            except httpx.TimeoutException as exc:
                raise GeminiServerError("Validation request timed out", status_code=504) from exc
            except httpx.RequestError as exc:
                clean_err = redact_api_key(str(exc), self.api_key)
                raise GeminiServerError(f"Network error during key validation: {clean_err}", status_code=502) from exc

        clean_resp = redact_api_key(response.text, self.api_key)
        if response.status_code == 200:
            return True
        elif response.status_code == 429 or "RESOURCE_EXHAUSTED" in clean_resp or "quota" in clean_resp.lower():
            # Quota exhausted: The key is VALID, but quota is reached
            raise GeminiRateLimitError("Gemini quota exceeded (key is valid but currently rate-limited or quota exhausted)")
        elif response.status_code in (400, 401, 403):
            raise GeminiAuthError("Invalid Gemini API key: authentication failed")
        elif response.status_code >= 500:
            raise GeminiServerError("Gemini server error during validation", status_code=response.status_code)
        else:
            raise GeminiError(f"Unexpected validation response ({response.status_code})", status_code=response.status_code)

    async def embed_content(
        self,
        text: str,
        model: str = "gemini-embedding-001",
    ) -> list[float]:
        if not self.api_key or self.api_key.strip() == "":
            raise GeminiAuthError("API key cannot be empty")

        target_model = (
            "gemini-embedding-001"
            if model in ("text-embedding-004", "embedding-001", "default")
            else model
        )
        url = f"{self.base_url}/{target_model}:embedContent?key={self.api_key}"
        payload = {
            "content": {
                "parts": [{"text": text}]
            }
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload)
            except httpx.TimeoutException as exc:
                raise GeminiServerError("Gemini embedding timed out", status_code=504) from exc
            except httpx.RequestError as exc:
                clean_err = redact_api_key(str(exc), self.api_key)
                raise GeminiServerError(
                    f"Network error during embedding: {clean_err}", status_code=502
                ) from exc

        clean_resp = redact_api_key(response.text, self.api_key)
        if response.status_code == 429:
            raise GeminiRateLimitError(clean_resp)
        elif response.status_code in (400, 401, 403):
            raise GeminiAuthError(f"Authentication failed: {clean_resp}")
        elif response.status_code >= 500:
            raise GeminiServerError(clean_resp, status_code=response.status_code)
        elif response.status_code != 200:
            raise GeminiError(
                f"Unexpected embedding error ({response.status_code}): {clean_resp}",
                status_code=response.status_code,
            )

        data = response.json()
        return data.get("embedding", {}).get("values", [])


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
        self.embeddings: dict[str, list[float]] = {}

        # Simulated failure counters & switches
        self.fail_429_count = 0
        self.fail_500_count = 0
        self.fail_embedding_count = 0
        self.fail_judge_json_once = False
        self.is_invalid_api_key = False
        self.is_quota_exhausted = False
        self.is_timeout = False

    def set_response_for_prompt(self, prompt_substring: str, response: str) -> None:
        """Map a substring to a specific response string."""
        self.prompt_responses[prompt_substring] = response

    set_response = set_response_for_prompt

    def set_judge_response(self, response: dict[str, Any] | str) -> None:
        """Convenience method to set response for LLM judge prompts."""
        import json

        text = json.dumps(response) if isinstance(response, dict) else str(response)
        self.prompt_responses["<evaluation_task>"] = text
        self.prompt_responses["<rubric>"] = text
        self.prompt_responses["not valid JSON"] = text
        self.prompt_responses["raw JSON object"] = text

    def set_embedding_for_text(self, text: str, vector: list[float]) -> None:
        """Program a deterministic embedding vector for given text."""
        self.embeddings[text] = vector

    def set_fail_with_429(self, count: int = 1) -> None:
        """Configure client to raise 429 for the next `count` calls."""
        self.fail_429_count = count

    def set_fail_with_500(self, count: int = 1) -> None:
        """Configure client to raise 500 for the next `count` calls."""
        self.fail_500_count = count

    def set_fail_embedding(self, count: int = 1) -> None:
        """Configure client to fail embed_content calls."""
        self.fail_embedding_count = count

    def set_fail_judge_json_once(self, enable: bool = True) -> None:
        """Simulate a malformed JSON response on the first judge call to test 1-time retry."""
        self.fail_judge_json_once = enable

    def set_invalid_api_key(self, is_invalid: bool = True) -> None:
        """Simulate invalid API key rejection."""
        self.is_invalid_api_key = is_invalid

    def set_quota_exhausted(self, is_exhausted: bool = True) -> None:
        self.is_quota_exhausted = is_exhausted

    def set_timeout(self, is_timeout: bool = True) -> None:
        self.is_timeout = is_timeout

    async def validate_key(self) -> bool:
        if self.is_timeout:
            raise GeminiServerError("Simulated validation timeout", status_code=504)
        if self.is_invalid_api_key:
            raise GeminiAuthError("Invalid Gemini API key provided")
        if self.is_quota_exhausted:
            raise GeminiRateLimitError("Quota exhausted for this key")
        if self.fail_500_count > 0:
            raise GeminiServerError("Simulated server error during key check", status_code=500)
        return True

    async def generate_content(
        self,
        prompt: str,
        model: str = "gemini-2.5-flash",
        temperature: float = 1.0,
        system_instruction: str | None = None,
        top_p: float | None = None,
        max_output_tokens: int | None = None,
        response_mime_type: str | None = None,
    ) -> GeminiResponse:
        self.calls.append(
            {
                "prompt": prompt,
                "model": model,
                "temperature": temperature,
                "system_instruction": system_instruction,
                "top_p": top_p,
                "max_output_tokens": max_output_tokens,
                "response_mime_type": response_mime_type,
                "timestamp": time.time(),
            }
        )

        if self.is_timeout:
            raise GeminiServerError("Simulated request timeout", status_code=504)

        if self.is_invalid_api_key:
            raise GeminiAuthError("Invalid Gemini API key provided")

        if self.is_quota_exhausted or self.fail_429_count > 0:
            if self.fail_429_count > 0:
                self.fail_429_count -= 1
            raise GeminiRateLimitError("Simulated 429 Too Many Requests")

        if self.fail_500_count > 0:
            self.fail_500_count -= 1
            raise GeminiServerError("Simulated 500 Internal Server Error", status_code=500)

        # Handle simulate malformed JSON once for judge retry testing
        if self.fail_judge_json_once and ("<evaluation_task>" in prompt or "rubric" in prompt):
            self.fail_judge_json_once = False
            return GeminiResponse(
                text="Malformed JSON: {passed: true, missing quotes}",
                prompt_tokens=20,
                completion_tokens=10,
                total_tokens=30,
                latency_ms=self.simulated_latency_ms,
            )

        # Matched response (sort keys descending by length so longer substrings match first)
        text = self.default_response
        sorted_pairs = sorted(
            self.prompt_responses.items(), key=lambda item: len(item[0]), reverse=True
        )
        for sub, resp in sorted_pairs:
            if sub in prompt:
                text = resp
                break

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

    async def embed_content(
        self,
        text: str,
        model: str = "gemini-embedding-001",
    ) -> list[float]:
        if self.fail_embedding_count > 0:
            self.fail_embedding_count -= 1
            raise GeminiServerError("Simulated embedding failure", status_code=500)

        if text in self.embeddings:
            return self.embeddings[text]

        dim = 16
        vec = [0.0] * dim
        words = text.lower().split()
        if not words:
            vec[0] = 1.0
            return vec

        for word in words:
            h = abs(hash(word))
            for i in range(dim):
                vec[i] += ((h >> (i * 2)) & 0xF) / 15.0 - 0.5

        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [round(x / norm, 6) for x in vec]
