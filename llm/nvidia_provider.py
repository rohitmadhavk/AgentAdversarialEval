"""
llm/nvidia_provider.py — NVIDIA NIM implementation of LLMProvider.

NVIDIA NIM exposes an OpenAI-compatible API so this is structurally
identical to GroqProvider with a different base_url and API key env var.

Get a free API key (no credit card): https://build.nvidia.com
Recommended model: meta/llama-3.3-70b-instruct

Rate limits (free tier): 40 RPM, 1000 RPD — generous enough for a full eval run.

Retry policy
────────────
429 rate limit  → exponential backoff, up to _MAX_RETRIES attempts.
400 bad request → if tool_use_failed, returns empty tool_calls immediately
                  (deterministic failure — retrying won't help).
"""

import json
import logging
import os
import time

from openai import BadRequestError, OpenAI, RateLimitError

from .base_provider import LLMProvider, LLMResponse, ToolCall

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_S = [20, 45, 65]  # 65s > 60s rolling window — 3rd retry always clears quota


class NvidiaProvider(LLMProvider):
    def __init__(self, model: str = "meta/llama-3.3-70b-instruct"):
        self._model = model
        self._client = OpenAI(
            api_key=os.environ["NVIDIA_API_KEY"],
            base_url="https://integrate.api.nvidia.com/v1",
        )

    @property
    def name(self) -> str:
        return f"nvidia/{self._model}"

    def complete(
        self,
        messages: list[dict],
        system_prompt: str,
        tool_schemas: list[dict],
    ) -> LLMResponse:
        oai_messages = _to_messages(messages, system_prompt)
        oai_tools = _to_tools(tool_schemas)

        backoff_total = 0.0
        for attempt in range(1 + _MAX_RETRIES):
            if attempt > 0:
                wait = _BACKOFF_S[attempt - 1]
                time.sleep(wait)
                backoff_total += wait
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=oai_messages,
                    tools=oai_tools,
                    tool_choice="auto",
                )
            except BadRequestError as exc:
                if "tool_use_failed" in str(exc):
                    # Deterministic model generation failure — retrying the same
                    # prompt reproduces the same failure. Return immediately.
                    logger.warning(
                        "tool_use_failed on attempt %d — returning empty tool_calls. raw: %s",
                        attempt + 1, exc,
                    )
                    return LLMResponse(text=None, tool_calls=[], stop_reason="end_turn", raw=exc, backoff_s=backoff_total)
                raise
            except RateLimitError as exc:
                if attempt == _MAX_RETRIES:
                    raise
                logger.warning(
                    "rate limit hit (attempt %d/%d), backing off %ds",
                    attempt + 1, 1 + _MAX_RETRIES, _BACKOFF_S[attempt],
                )
                continue
            break

        choice = response.choices[0]
        msg = choice.message

        tool_calls = [
            ToolCall(
                id=tc.id,
                name=tc.function.name,
                input=json.loads(tc.function.arguments),
            )
            for tc in (msg.tool_calls or [])
        ]

        return LLMResponse(
            text=msg.content or None,
            tool_calls=tool_calls,
            stop_reason="tool_use" if tool_calls else "end_turn",
            raw=response,
            backoff_s=backoff_total,
        )


def _to_tools(schemas: list[dict]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name":        s["name"],
                "description": s["description"],
                "parameters":  s["parameters"],
            },
        }
        for s in schemas
    ]


def _to_messages(messages: list[dict], system_prompt: str) -> list[dict]:
    out = [{"role": "system", "content": system_prompt}]

    for msg in messages:
        role = msg["role"]

        if role == "user":
            out.append({"role": "user", "content": msg["content"]})

        elif role == "assistant":
            assistant_msg: dict = {"role": "assistant", "content": msg.get("content") or None}
            if "_tool_calls" in msg:
                assistant_msg["tool_calls"] = [
                    {
                        "id":       tc["id"],
                        "type":     "function",
                        "function": {
                            "name":      tc["name"],
                            "arguments": json.dumps(tc["input"]),
                        },
                    }
                    for tc in msg["_tool_calls"]
                ]
            out.append(assistant_msg)

        elif role == "tool":
            out.append({
                "role":         "tool",
                "tool_call_id": msg["tool_use_id"],
                "content":      msg["content"],
            })

    return out
