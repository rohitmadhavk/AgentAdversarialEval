"""
llm/base_provider.py — abstract interface every LLM provider must implement.

The agent loop only ever talks to an LLMProvider. It never imports
anthropic, google.generativeai, or any other SDK directly.

Normalised response contract
─────────────────────────────
Every provider returns an LLMResponse with:

    text          str | None      — final text to show the user
    tool_calls    list[ToolCall]  — tool invocations requested by the model
    stop_reason   str             — "end_turn" | "tool_use" | "error"
    raw                          — original SDK response (for debugging)

Normalised message format
─────────────────────────
Messages passed into complete() use a provider-agnostic dict format:

    {"role": "user",      "content": "hello"}
    {"role": "assistant", "content": "hi!"}
    {"role": "tool",      "tool_use_id": "abc", "name": "calculate", "content": "42"}

Each provider's complete() is responsible for translating this into
whatever its SDK expects before sending, and translating the response back.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """A single tool invocation requested by the model."""
    id:    str
    name:  str
    input: dict[str, Any]


@dataclass
class LLMResponse:
    """Normalised response returned by every provider."""
    text:        str | None
    tool_calls:  list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"   # "end_turn" | "tool_use" | "error"
    raw:         Any = None         # original SDK object, useful for debugging
    backoff_s:   float = 0.0        # cumulative time spent in rate-limit backoff waits


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    Subclass this and implement complete() to add a new provider.
    The agent loop never needs to change.
    """

    @abstractmethod
    def complete(
        self,
        messages:      list[dict],
        system_prompt: str,
        tool_schemas:  list[dict],
    ) -> LLMResponse:
        """
        Send messages to the model and return a normalised LLMResponse.

        Args:
            messages:      conversation history in provider-agnostic format
            system_prompt: system instruction string
            tool_schemas:  list of tool definitions in Anthropic schema format
                           (providers translate these to their own format internally)

        Returns:
            LLMResponse with text, tool_calls, and stop_reason populated.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name, used in logs and eval reports."""
        ...
