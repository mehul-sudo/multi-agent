"""
OpenAI LLM Provider Adapter.

Maps normalized LLMRequest/LLMResponse objects to OpenAI API specifications.
Translates OpenAI SDK errors into normalized exception taxonomy.
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


class OpenAIProviderAdapter(LLMProvider):
    """Adapter for OpenAI models (e.g. gpt-4o, gpt-4o-mini, gpt-3.5-turbo)."""

    def __init__(self, api_key: Optional[str] = None, client: Any = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._client = client

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def supported_models(self) -> List[str]:
        return ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]

    def validate_config(self) -> bool:
        return bool(self.api_key)

    def supports_capability(self, capability: str) -> bool:
        supported = {"text", "json_mode", "tools", "streaming", "structured_output"}
        return capability in supported

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Execute request against OpenAI API or mocked SDK client."""
        if not self.validate_config() and not self._client:
            raise LLMConfigurationError(
                "OpenAI API key is missing. Export OPENAI_API_KEY in environment.",
                provider=self.provider_name,
                model=request.model,
            )

        request.validate_limits()
        start_time = time.time()

        # Format messages for OpenAI
        formatted_messages = []
        if request.system_instructions:
            formatted_messages.append({"role": "system", "content": request.system_instructions})

        for msg in request.messages:
            m_dict = {"role": msg.role, "content": msg.content}
            if msg.name:
                m_dict["name"] = msg.name
            if msg.tool_calls:
                m_dict["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                m_dict["tool_call_id"] = msg.tool_call_id
            formatted_messages.append(m_dict)

        # Format tools if provided
        formatted_tools = None
        if request.tools:
            formatted_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in request.tools
            ]

        # Call OpenAI SDK client if passed, or simulate clean output if mocked in tests
        try:
            if self._client:
                # Use injected client (for unit tests / mock SDK)
                res = self._client.chat.completions.create(
                    model=request.model,
                    messages=formatted_messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    tools=formatted_tools,
                    timeout=request.timeout,
                )
                return self._parse_openai_response(res, start_time)
            else:
                # Direct API invocation or SDK import
                import openai
                client = openai.OpenAI(api_key=self.api_key)
                kwargs: Dict[str, Any] = {
                    "model": request.model,
                    "messages": formatted_messages,
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                }
                if formatted_tools:
                    kwargs["tools"] = formatted_tools
                if request.response_format == "json":
                    kwargs["response_format"] = {"type": "json_object"}
                # Pass the normalized timeout to the OpenAI SDK.
                # The openai SDK accepts timeout as a float (seconds) or
                # httpx.Timeout object.  A float is sufficient here.
                kwargs["timeout"] = request.timeout

                res = client.chat.completions.create(**kwargs)
                parsed = self._parse_openai_response(res, start_time)
                self._maybe_record_usage(request, parsed)
                return parsed
        except Exception as exc:
            self._handle_exception(exc, request.model)

    def _parse_openai_response(self, response: Any, start_time: float) -> LLMResponse:
        duration_ms = int((time.time() - start_time) * 1000)

        # Handle object or dict response
        if isinstance(response, dict):
            choice = response["choices"][0]
            msg = choice["message"]
            text = msg.get("content") or ""
            finish_reason = choice.get("finish_reason", "stop")
            usage_data = response.get("usage", {})
            req_id = response.get("id")
        else:
            choice = response.choices[0]
            msg = choice.message
            text = msg.content or ""
            finish_reason = getattr(choice, "finish_reason", "stop")
            usage_data = getattr(response, "usage", None)
            req_id = getattr(response, "id", None)

        tool_calls = []
        raw_tc = getattr(msg, "tool_calls", None) if not isinstance(msg, dict) else msg.get("tool_calls")
        if raw_tc:
            for tc in raw_tc:
                if isinstance(tc, dict):
                    tc_id = tc.get("id", "")
                    fn = tc.get("function", {})
                    fn_name = fn.get("name", "")
                    fn_args = fn.get("arguments", "{}")
                else:
                    tc_id = tc.id
                    fn_name = tc.function.name
                    fn_args = tc.function.arguments

                if isinstance(fn_args, str):
                    try:
                        parsed_args = json.loads(fn_args)
                    except Exception:
                        parsed_args = {"raw": fn_args}
                else:
                    parsed_args = fn_args

                tool_calls.append(LLMToolCall(id=tc_id, name=fn_name, arguments=parsed_args))

        json_data = None
        if text.strip().startswith("{") and text.strip().endswith("}"):
            try:
                json_data = json.loads(text)
            except Exception:
                pass

        if isinstance(usage_data, dict):
            p_tok = usage_data.get("prompt_tokens", 0)
            c_tok = usage_data.get("completion_tokens", 0)
            t_tok = usage_data.get("total_tokens", 0)
        elif usage_data:
            p_tok = getattr(usage_data, "prompt_tokens", 0)
            c_tok = getattr(usage_data, "completion_tokens", 0)
            t_tok = getattr(usage_data, "total_tokens", 0)
        else:
            p_tok, c_tok, t_tok = 0, 0, 0

        return LLMResponse(
            provider=self.provider_name,
            model=response.model if hasattr(response, "model") else "openai-model",
            text=text,
            json_data=json_data,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=LLMUsage(prompt_tokens=p_tok, completion_tokens=c_tok, total_tokens=t_tok),
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
            raise LLMAuthenticationError(f"OpenAI authentication failed: {err_msg}", provider=self.provider_name, model=model)
        elif "RateLimit" in err_type or "429" in err_msg:
            raise LLMRateLimitError(f"OpenAI rate limit exceeded: {err_msg}", provider=self.provider_name, model=model)
        elif "Timeout" in err_type or "timed out" in err_msg.lower():
            raise LLMTimeoutError(f"OpenAI request timed out: {err_msg}", provider=self.provider_name, model=model)
        elif "InvalidRequest" in err_type or "400" in err_msg:
            raise LLMInvalidRequestError(f"OpenAI invalid request: {err_msg}", provider=self.provider_name, model=model)
        elif "ServiceUnavailable" in err_type or "500" in err_msg or "503" in err_msg:
            raise LLMProviderUnavailableError(f"OpenAI service unavailable: {err_msg}", provider=self.provider_name, model=model)
        else:
            raise LLMProviderUnavailableError(f"OpenAI error ({err_type}): {err_msg}", provider=self.provider_name, model=model)
