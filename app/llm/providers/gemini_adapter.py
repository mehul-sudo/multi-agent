"""
Google Gemini LLM Provider Adapter.

Maps normalized LLMRequest/LLMResponse objects to Google Gemini API specifications.
Translates Gemini SDK exceptions into normalized exception taxonomy.
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


class GeminiProviderAdapter(LLMProvider):
    """Adapter for Google Gemini models (e.g. gemini-flash-lite-latest, gemini-3.5-flash, gemini-2.5-flash)."""

    def __init__(self, api_key: Optional[str] = None, client: Any = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self._client = client

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def supported_models(self) -> List[str]:
        return [
            "gemini-flash-lite-latest",
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-3-flash-preview",
            "gemini-3.8-flash",
            "gemini-flash-latest",
            "gemini-pro-latest",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.5-flash-lite",
        ]

    def validate_config(self) -> bool:
        return bool(self.api_key)

    def supports_capability(self, capability: str) -> bool:
        supported = {"text", "json_mode", "tools", "streaming", "structured_output"}
        return capability in supported

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Execute request against Gemini API or mocked SDK client."""
        if not self.validate_config() and not self._client:
            raise LLMConfigurationError(
                "Gemini API key is missing. Export GEMINI_API_KEY or GOOGLE_API_KEY in environment.",
                provider=self.provider_name,
                model=request.model,
            )

        request.validate_limits()
        start_time = time.time()

        # Format prompt
        contents = []
        if request.system_instructions:
            contents.append(f"System: {request.system_instructions}")

        for msg in request.messages:
            contents.append(f"{msg.role.capitalize()}: {msg.content}")

        full_prompt = "\n\n".join(contents) if contents else "Execute task."

        try:
            if self._client:
                # Injected-client path (unit tests / mocks).
                # The mock client is expected to accept timeout as a keyword
                # argument for test-verifiability.
                res = self._client.generate_content(
                    contents=full_prompt,
                    generation_config={"temperature": request.temperature, "max_output_tokens": request.max_tokens},
                    timeout=request.timeout,
                )
                parsed = self._parse_gemini_response(res, request.model, start_time)
                self._maybe_record_usage(request, parsed)
                return parsed
            else:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)

                # Pool of verified active Gemini models with automatic fallback on quota exhaustion (429), retirement (404), or timeout (504)
                configured_model = os.getenv("GEMINI_MODEL") or "gemini-flash-lite-latest"
                candidates = [
                    configured_model,
                    "gemini-flash-lite-latest",
                    "gemini-3.5-flash",
                    "gemini-3.5-flash-lite",
                    "gemini-3-flash-preview",
                    "gemini-3.8-flash",
                    request.model,
                ]
                active_candidates = []
                for m in candidates:
                    if m and m not in active_candidates:
                        active_candidates.append(m)

                config = {
                    "temperature": request.temperature,
                    "max_output_tokens": request.max_tokens,
                }
                if request.response_format == "json":
                    config["response_mime_type"] = "application/json"

                last_exc = None
                call_timeout = float(getattr(request, "timeout", 15.0) or 15.0)
                for candidate in active_candidates:
                    try:
                        model_inst = genai.GenerativeModel(candidate)
                        res = model_inst.generate_content(
                            full_prompt,
                            generation_config=config,
                            request_options={"timeout": call_timeout},
                        )
                        parsed = self._parse_gemini_response(res, candidate, start_time)
                        self._maybe_record_usage(request, parsed)
                        return parsed
                    except Exception as inner_exc:
                        last_exc = inner_exc
                        err_str = str(inner_exc).lower()
                        # If quota exceeded (429), not found (404), or timeout (504), transparently try the next model
                        if any(k in err_str for k in ("quota", "429", "rate limit", "not found", "404", "exhausted", "deadline", "timed out", "504")):
                            continue
                        raise inner_exc

                if last_exc:
                    raise last_exc
        except Exception as exc:
            self._handle_exception(exc, request.model)

    def _parse_gemini_response(self, response: Any, model: str, start_time: float) -> LLMResponse:
        import uuid
        duration_ms = int((time.time() - start_time) * 1000)

        metadata_available = True
        if isinstance(response, dict):
            text_content = response.get("text", "")
            usage_dict = response.get("usage", {})
            if usage_dict:
                p_tok = int(usage_dict.get("prompt_tokens") or usage_dict.get("prompt_token_count") or 0)
                c_tok = int(usage_dict.get("completion_tokens") or usage_dict.get("candidates_token_count") or 0)
                t_tok = int(usage_dict.get("total_tokens") or usage_dict.get("total_token_count") or (p_tok + c_tok))
            else:
                p_tok, c_tok, t_tok = 0, 0, 0
                metadata_available = False
        else:
            text_content = ""
            try:
                text_content = getattr(response, "text", "")
            except Exception:
                pass
            if not text_content and hasattr(response, "candidates") and response.candidates:
                parts_text = []
                for cand in response.candidates:
                    content = getattr(cand, "content", None)
                    if content:
                        for p in getattr(content, "parts", []):
                            t = getattr(p, "text", "")
                            if t:
                                parts_text.append(t)
                text_content = "".join(parts_text)

            usage_meta = getattr(response, "usage_metadata", None)
            if usage_meta:
                def _extract_token_count(val):
                    if val is None:
                        return 0
                    if isinstance(val, (int, float)):
                        return int(val)
                    if "Mock" in str(type(val)):
                        return 0
                    try:
                        return int(val)
                    except (ValueError, TypeError):
                        return 0

                p_tok = _extract_token_count(getattr(usage_meta, "prompt_token_count", None))
                c_tok = _extract_token_count(getattr(usage_meta, "candidates_token_count", None))
                raw_total = getattr(usage_meta, "total_token_count", None)
                t_tok = _extract_token_count(raw_total)
                if t_tok < (p_tok + c_tok):
                    t_tok = p_tok + c_tok
                metadata_available = True
            else:
                p_tok = 0
                c_tok = 0
                t_tok = 0
                metadata_available = False

        json_data = None
        if text_content.strip().startswith("{") and text_content.strip().endswith("}"):
            try:
                json_data = json.loads(text_content)
            except Exception:
                pass

        return LLMResponse(
            provider=self.provider_name,
            model=model,
            text=text_content,
            json_data=json_data,
            tool_calls=[],
            finish_reason="stop",
            usage=LLMUsage(
                prompt_tokens=p_tok,
                completion_tokens=c_tok,
                total_tokens=t_tok if t_tok else (p_tok + c_tok),
                metadata_available=metadata_available,
            ),
            request_duration_ms=duration_ms,
            provider_request_id=f"gemini_req_{uuid.uuid4().hex[:12]}",
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

    def _sanitize_error_message(self, msg: str) -> str:
        """Sanitize error messages so that API keys and secrets are never exposed."""
        import re
        sanitized = re.sub(r'key=[A-Za-z0-9_\-\.]+', 'key=[REDACTED]', msg)
        sanitized = re.sub(r'AIza[A-Za-z0-9_\-]{35}', '[REDACTED_API_KEY]', sanitized)
        sanitized = re.sub(r'AQ\.[A-Za-z0-9_\-]{30,}', '[REDACTED_API_KEY]', sanitized)
        return sanitized

    def _handle_exception(self, exc: Exception, model: str) -> None:
        raw_msg = str(exc)
        err_msg = self._sanitize_error_message(raw_msg)
        err_type = exc.__class__.__name__

        if "APIKey" in err_type or "api_key" in raw_msg.lower() or "401" in raw_msg or "unauthorized" in raw_msg.lower():
            raise LLMAuthenticationError(f"Gemini authentication failed: {err_msg}", provider=self.provider_name, model=model)
        elif "ResourceExhausted" in err_type or "429" in raw_msg or "quota" in raw_msg.lower():
            raise LLMRateLimitError(f"Gemini rate limit or quota exceeded: {err_msg}", provider=self.provider_name, model=model)
        elif "DeadlineExceeded" in err_type or "timeout" in raw_msg.lower():
            raise LLMTimeoutError(f"Gemini request timed out: {err_msg}", provider=self.provider_name, model=model)
        elif "InvalidArgument" in err_type or "400" in raw_msg:
            raise LLMInvalidRequestError(f"Gemini invalid request: {err_msg}", provider=self.provider_name, model=model)
        else:
            raise LLMProviderUnavailableError(f"Gemini error ({err_type}): {err_msg}", provider=self.provider_name, model=model)
