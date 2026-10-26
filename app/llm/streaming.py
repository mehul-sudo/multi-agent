"""
Streaming Architecture for Normalized LLM Responses.

Provides a unified streaming chunk container and accumulator for streaming tokens
from OpenAI, Anthropic, Gemini, or Mock providers.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Generator, Optional

from app.llm.contracts import LLMResponse, LLMUsage


@dataclass
class LLMStreamChunk:
    """A single streaming token/chunk event."""

    delta_text: str
    is_final: bool = False
    finish_reason: Optional[str] = None
    usage: Optional[LLMUsage] = None
    provider: str = "mock"
    model: str = "mock-v1"


class LLMStreamAccumulator:
    """Accumulates streaming chunks into a final complete LLMResponse object."""

    def __init__(self, provider: str, model: str):
        self.provider = provider
        self.model = model
        self.accumulated_text: str = ""
        self.finish_reason: str = "stop"
        self.usage: LLMUsage = LLMUsage()

    def process_chunk(self, chunk: LLMStreamChunk) -> None:
        """Accumulate delta text and capture final usage metadata."""
        if chunk.delta_text:
            self.accumulated_text += chunk.delta_text
        if chunk.finish_reason:
            self.finish_reason = chunk.finish_reason
        if chunk.usage:
            self.usage = chunk.usage

    def to_response(self, request_duration_ms: int = 0) -> LLMResponse:
        """Produce the final assembled LLMResponse from streamed chunks."""
        prompt_tok = self.usage.prompt_tokens or max(1, len(self.accumulated_text.split()))
        comp_tok = self.usage.completion_tokens or max(1, len(self.accumulated_text.split()))
        tot_tok = prompt_tok + comp_tok

        return LLMResponse(
            provider=self.provider,
            model=self.model,
            text=self.accumulated_text,
            finish_reason=self.finish_reason,
            usage=LLMUsage(
                prompt_tokens=prompt_tok,
                completion_tokens=comp_tok,
                total_tokens=tot_tok,
            ),
            request_duration_ms=request_duration_ms,
            is_streaming=True,
        )
