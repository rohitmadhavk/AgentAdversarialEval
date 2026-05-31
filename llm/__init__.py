"""
llm/__init__.py — provider factory.

Default: Groq LPU (openai/gpt-oss-120b) — fast inference, free tier (no credit card).
Groq's server-side schema validation rejects integer fields sent as strings; the
GroqProvider handles this via client-side type coercion in the BadRequestError handler.

Override at runtime via env vars:
  GROQ_MODEL=llama-3.3-70b-versatile make run   # swap Groq model
  NVIDIA_API_KEY=... make run                    # uncomment NvidiaProvider below
"""

import os

from .groq_provider import GroqProvider
from .base_provider import LLMProvider, LLMResponse, ToolCall
from .gemini_provider import GeminiProvider
from .nvidia_provider import NvidiaProvider

__all__ = ["get_provider", "LLMProvider", "LLMResponse", "ToolCall"]


def get_provider() -> LLMProvider:
    return GroqProvider(model=os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"))
    # return GeminiProvider(model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"))
    # return NvidiaProvider(model=os.environ.get("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct"))
