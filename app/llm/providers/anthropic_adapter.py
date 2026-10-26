"""
Anthropic Claude LLM Provider Adapter.

Maps normalized LLMRequest/LLMResponse objects to Anthropic Claude Messages API specifications.
Translates Anthropic SDK exceptions into normalized exception taxonomy.
"""

import json
import os
import time
from typing import Any, Dict, List, Optional

from app.llm.base import LLMProvider
from app.llm.contracts import LLMRequest, LLMResponse, LLMToolCall, LLMUsage
from app.llm.errors import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMInvalidRequestError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMProviderUnavailableError,
)


class AnthropicProviderAdapter(LLMProvider):
    """Adapter for Anthropic Claude models (e.g. claude-3-5-sonnet, claude-3-haiku, claude-3-opus)."""

    def __init__(self, api_key: Optional[str] = None, client: Any = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client = client

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def supported_models(self) -> List[str]:
        return ["claude-3-5-sonnet-20240620", "claude-3-opus-20240229", "claude-3-haiku-20240307"]

    def validate_config(self) -> bool:
        return bool(self.api_key)

    def supports_capability(self, capability: str) -> bool:
        supported = {"text", "json_mode", "tools", "streaming", "structured_output"}
        return capability in supported

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Execute request against Anthropic API or mocked SDK client."""
        if not self.validate_config() and not self._client:
            raise LLMConfigurationError(
                "Anthropic API key is missing. Export ANTHROPIC_API_KEY in environment.",
                provider=self.provider_name,
                model=request.model,
            )

        request.validate_limits()
        start_time = time.time()

        # Format system prompt separately for Anthropic
        system_prompt = request.system_instructions or ""

        # Format messages (excluding system role which is passed separately in Anthropic)
        formatted_messages = []
        for msg in request.messages:
            if msg.role != "system":
                formatted_messages.append({"role": msg.role, "content": msg.content})

        if not formatted_messages:
            formatted_messages.append({"role": "user", "content": "Execute task."})

        # Format tools for Anthropic
        formatted_tools = None
        if request.tools:
            formatted_tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.parameters,
                }
                for tool in request.tools
            ]

        try:
            if self._client:
                res = self._client.messages.create(
                    model=request.model,
                    system=system_prompt,
                    messages=formatted_messages,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                    tools=formatted_tools,
                    timeout=request.timeout,
                )
                return self._parse_anthropic_response(res, start_time)
            else:
                import anthropic
                client = anthropic.Anthropic(api_key=self.api_key)
                kwargs: Dict[str, Any] = {
                    "model": request.model,
                    "system": system_prompt,
                    "messages": formatted_messages,
                    "max_tokens": request.max_tokens,
                    "temperature": request.temperature,
                }
                if formatted_tools:
                    kwargs["tools"] = formatted_tools
                # Pass the normalized timeout to the Anthropic SDK.
                # The anthropic SDK accepts timeout as a float (seconds).
                kwargs["timeout"] = request.timeout

                res = client.messages.create(**kwargs)
                parsed = self._parse_anthropic_response(res, start_time)
                self._maybe_record_usage(request, parsed)
                return parsed
        except Exception as exc:
            self._handle_exception(exc, request.model)

    def _parse_anthropic_response(self, response: Any, start_time: float) -> LLMResponse:
        duration_ms = int((time.time() - start_time) * 1000)

        text_content = ""
        tool_calls = []

        if isinstance(response, dict):
            content_list = response.get("content", [])
            finish_reason = response.get("stop_reason", "end_turn")
            usage_data = response.get("usage", {})
            req_id = response.get("id")

            for block in content_list:
                if block.get("type") == "text":
                    text_content += block.get("text", "")
                elif block.get("type") == "tool_use":
                    tool_calls.append(
                        LLMToolCall(
                            id=block.get("id", ""),
                            name=block.get("name", ""),
                            arguments=block.get("input", {}),
                        )
                    )
        else:
            content_list = getattr(response, "content", [])
            finish_reason = getattr(response, "stop_reason", "end_turn")
            usage_data = getattr(response, "usage", None)
            req_id = getattr(response, "id", None)

            for block in content_list:
                b_type = getattr(block, "type", "")
                if b_type == "text":
                    text_content += getattr(block, "text", "")
                elif b_type == "tool_use":
                    tool_calls.append(
                        LLMToolCall(
                            id=getattr(block, "id", ""),
                            name=getattr(block, "name", ""),
                            arguments=getattr(block, "input", {}),
                        )
                    )

        json_data = None
        if text_content.strip().startswith("{") and text_content.strip().endswith("}"):
            try:
                json_data = json.loads(text_content)
            except Exception:
                pass

        if isinstance(usage_data, dict):
            p_tok = usage_data.get("input_tokens", 0)
            c_tok = usage_data.get("output_tokens", 0)
        elif usage_data:
            p_tok = getattr(usage_data, "input_tokens", 0)
            c_tok = getattr(usage_data, "output_tokens", 0)
        else:
            p_tok, c_tok = 0, 0

        return LLMResponse(
            provider=self.provider_name,
            model=getattr(response, "model", "claude-model") if not isinstance(response, dict) else response.get("model", "claude-model"),
            text=text_content,
            json_data=json_data,
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else str(finish_reason),
            usage=LLMUsage(prompt_tokens=p_tok, completion_tokens=c_tok, total_tokens=p_tok + c_tok),
            request_duration_ms=duration_ms,
            provider_request_id=req_id,
        )

    def _maybe_record_usage(self, request: LLMRequest, response: LLMResponse) -> None:
        """Persist accurate token usage into LLMUsageLog when inside Flask app context."""
        if not request or getattr(request, "skip_usage_logging", False):
            return
        try:
            from flask import has_app_context
            if has_app_context():
                from app.services.llm_usage_service import record_llm_response_usage
                record_llm_response_usage(request, response)
        except Exception:
            pass

    def _handle_exception(self, exc: Exception, model: str) -> None:
        err_msg = str(exc)
        err_type = exc.__class__.__name__

        if "Authentication" in err_type or "api_key" in err_msg.lower() or "401" in err_msg:
            raise LLMAuthenticationError(f"Anthropic authentication failed: {err_msg}", provider=self.provider_name, model=model)
        elif "RateLimit" in err_type or "429" in err_msg:
            raise LLMRateLimitError(f"Anthropic rate limit exceeded: {err_msg}", provider=self.provider_name, model=model)
        elif "Timeout" in err_type or "timed out" in err_msg.lower():
            raise LLMTimeoutError(f"Anthropic request timed out: {err_msg}", provider=self.provider_name, model=model)
        elif "InvalidRequest" in err_type or "400" in err_msg:
            raise LLMInvalidRequestError(f"Anthropic invalid request: {err_msg}", provider=self.provider_name, model=model)
        else:
            raise LLMProviderUnavailableError(f"Anthropic error ({err_type}): {err_msg}", provider=self.provider_name, model=model)
