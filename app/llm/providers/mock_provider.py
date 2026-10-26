"""
Deterministic Mock LLM Provider.

Does not require real API keys. Supports simulated latency, rate-limits, errors,
structured JSON output, tool calling, and token usage calculation for unit/integration tests.
"""

import json
import time
from typing import Any, Dict, List

from app.llm.base import LLMProvider
from app.llm.contracts import LLMRequest, LLMResponse, LLMToolCall, LLMUsage
from app.llm.errors import (
    LLMAuthenticationError,
    LLMInvalidRequestError,
    LLMRateLimitError,
    LLMTimeoutError,
)


class MockLLMProvider(LLMProvider):
    """Deterministic local mock LLM provider."""

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def supported_models(self) -> List[str]:
        return ["mock-v1", "mock-pro-v1", "mock-fast-v1"]

    def validate_config(self) -> bool:
        return True

    def supports_capability(self, capability: str) -> bool:
        supported = {"text", "json_mode", "tools", "streaming", "structured_output"}
        return capability in supported

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate deterministic mock response based on request & metadata controls."""
        request.validate_limits()

        # Simulated failure flags in request.metadata or request.messages
        meta = request.metadata or {}
        if meta.get("simulate_failure"):
            raise LLMTransientError(meta.get("failure_reason", "Simulated task execution failure."), provider=self.provider_name, model=request.model)
        if meta.get("simulate_auth_error"):
            raise LLMAuthenticationError("Simulated invalid API key.", provider=self.provider_name, model=request.model)
        if meta.get("simulate_rate_limit"):
            raise LLMRateLimitError("Simulated rate limit exceeded.", provider=self.provider_name, model=request.model, suggested_retry_delay=1.0)
        if meta.get("simulate_timeout"):
            raise LLMTimeoutError("Simulated API request timeout.", provider=self.provider_name, model=request.model)

        start_time = time.time()

        # Simulated latency
        latency_ms = meta.get("simulate_latency_ms", 10)
        time.sleep(latency_ms / 1000.0)

        # Content generation logic
        prompt_text = " ".join(m.content for m in request.messages)
        if request.system_instructions:
            prompt_text = f"{request.system_instructions} {prompt_text}"

        prompt_tokens = max(1, len(prompt_text.split()))

        generated_text = ""
        json_data = None
        tool_calls: List[LLMToolCall] = []

        if request.response_format == "json" or request.json_schema:
            json_data = {
                "status": "success",
                "message": "Mock JSON response",
                "processed_prompt_words": prompt_tokens,
                "model": request.model,
            }
            if meta.get("custom_json_output"):
                json_data = meta["custom_json_output"]
            generated_text = json.dumps(json_data)
        elif request.tools and meta.get("simulate_tool_call"):
            tc_info = meta.get("simulate_tool_call", {})
            tc = LLMToolCall(
                id=tc_info.get("id", "call_mock_123"),
                name=tc_info.get("name", request.tools[0].name),
                arguments=tc_info.get("arguments", {"query": "mock_query"}),
            )
            tool_calls.append(tc)
            generated_text = f"Invoking tool {tc.name}"
        else:
            if meta.get("custom_text_output"):
                generated_text = meta["custom_text_output"]
            else:
                generated_text = f"Mock LLM response for model [{request.model}] with prompt length {len(prompt_text)}."

        completion_tokens = max(1, len(generated_text.split()))
        total_tokens = prompt_tokens + completion_tokens

        end_time = time.time()
        duration_ms = int((end_time - start_time) * 1000)

        return LLMResponse(
            provider=self.provider_name,
            model=request.model,
            text=generated_text,
            json_data=json_data,
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else "stop",
            usage=LLMUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            ),
            request_duration_ms=duration_ms,
            provider_request_id=f"mock_req_{int(time.time())}",
            retry_count=0,
            is_streaming=request.streaming,
            raw_metadata={"mock": True},
        )
