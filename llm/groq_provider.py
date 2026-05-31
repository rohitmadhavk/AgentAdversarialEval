"""
llm/groq_provider.py — Groq implementation of LLMProvider.

Uses the official groq package (pip install groq).
Tool schemas arrive in Gemini format (name/description/parameters)
and are translated to OpenAI-style function definitions internally.

Get a free API key (no credit card): https://console.groq.com/keys
Recommended model: llama-3.3-70b-versatile (30 RPM free tier)

Retry policy
────────────
429 per-minute rate limit  → exponential backoff, up to _MAX_RETRIES attempts.
429 daily token quota      → surfaced immediately (retrying won't help).
400 tool_use_failed        → Groq validates schema types server-side. Two sub-cases:
                             (a) type mismatch (e.g. integer sent as string) — recoverable;
                                 client-side type coercion applied, call retried as valid.
                             (b) structurally malformed generation — unrecoverable;
                                 returned as empty tool_calls so agent falls back to text.
"""

import json
import logging
import os
import time
import uuid

from groq import BadRequestError, Groq, RateLimitError

from .base_provider import LLMProvider, LLMResponse, ToolCall

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_S = [2, 4, 8]   # waits before attempt 2, 3, 4


def _rescue_type_coercion(exc: BadRequestError, tool_schemas: list[dict]) -> list[ToolCall] | None:
    """Recover from Groq tool_use_failed when the only error is a string/integer type mismatch.

    Groq validates schema types server-side and rejects calls where the model emits
    e.g. "task_id": "1" (string) instead of "task_id": 1 (integer). The tool selection
    was correct — only the JSON value type is wrong. Parse failed_generation from the
    error body, coerce types to match the schema, and return corrected ToolCalls.

    Returns None if the generation is structurally malformed or coercion fails.
    """
    try:
        failed_gen = (exc.body or {}).get("error", {}).get("failed_generation")
        if not failed_gen:
            return None

        # Only handle the JSON-list format — type mismatches and "omit" sentinels.
        # Structurally malformed generations (e.g. broken closing tags) are left
        # unrecoverable and logged as genuine model failures.
        try:
            calls = json.loads(failed_gen)
        except (json.JSONDecodeError, ValueError):
            return None
        if not isinstance(calls, list):
            return None

        schema_map = {
            s["name"]: s["parameters"]["properties"]
            for s in tool_schemas
        }
        result = []
        for call in calls:
            name = call.get("name")
            params = dict(call.get("parameters", {}))
            drop_keys = []
            for k, v in params.items():
                prop = schema_map.get(name, {}).get(k, {})
                if prop.get("type") == "integer" and isinstance(v, str):
                    try:
                        params[k] = int(v)
                    except (ValueError, TypeError):
                        drop_keys.append(k)
                elif prop.get("type") == "number" and isinstance(v, str):
                    try:
                        params[k] = float(v)
                    except (ValueError, TypeError):
                        drop_keys.append(k)
            for k in drop_keys:
                del params[k]
            result.append(ToolCall(id=str(uuid.uuid4()), name=name, input=params))
        return result
    except Exception:
        return None


class GroqProvider(LLMProvider):
    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        self._model = model
        self._client = Groq(api_key=os.environ["GROQ_API_KEY"])

    @property
    def name(self) -> str:
        return f"groq/{self._model}"

    def complete(
        self,
        messages: list[dict],
        system_prompt: str,
        tool_schemas: list[dict],
    ) -> LLMResponse:
        groq_messages = _to_messages(messages, system_prompt)
        groq_tools = _to_groq_tools(tool_schemas)

        backoff_total = 0.0
        for attempt in range(1 + _MAX_RETRIES):
            if attempt > 0:
                wait = _BACKOFF_S[attempt - 1]
                time.sleep(wait)
                backoff_total += wait
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=groq_messages,
                    tools=groq_tools,
                    tool_choice="auto",
                    parallel_tool_calls=False
                )
            except BadRequestError as exc:
                if "tool_use_failed" in str(exc):
                    # Attempt type coercion first — Groq rejects e.g. "task_id": "1"
                    # (string) when schema declares integer. The model selected the
                    # right tool; only the JSON value type is wrong. Fix and reuse.
                    rescued = _rescue_type_coercion(exc, tool_schemas)
                    if rescued is not None:
                        logger.warning(
                            "tool_use_failed: rescued %d call(s) via type coercion",
                            len(rescued),
                        )
                        return LLMResponse(text=None, tool_calls=rescued, stop_reason="tool_use", raw=exc, backoff_s=backoff_total)
                    # Structurally malformed generation — unrecoverable.
                    logger.warning(
                        "tool_use_failed on attempt %d — unrecoverable, falling back to text. raw: %s",
                        attempt + 1, exc,
                    )
                    return LLMResponse(text=None, tool_calls=[], stop_reason="end_turn", raw=exc, backoff_s=backoff_total)
                raise
            except RateLimitError as exc:
                # Daily token quota (type=tokens) cannot be resolved by waiting;
                # surface it immediately so the eval harness records it as a crash.
                if "tokens" in str(exc) or attempt == _MAX_RETRIES:
                    raise
                logger.warning(
                    "per-minute rate limit hit (attempt %d/%d), backing off %ds",
                    attempt + 1, 1 + _MAX_RETRIES, _BACKOFF_S[attempt],
                )
                continue
            break

        choice = response.choices[0]
        msg = choice.message

        text = msg.content or None

        tool_calls = [
            ToolCall(
                id=tc.id,
                name=tc.function.name,
                input=json.loads(tc.function.arguments),
            )
            for tc in (msg.tool_calls or [])
        ]

        stop_reason = "tool_use" if tool_calls else "end_turn"

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            raw=response,
            backoff_s=backoff_total,
        )


def _to_groq_tools(schemas: list[dict]) -> list[dict]:
    """Translate from our internal schema format to Groq's OpenAI-style format."""
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
    """
    Translate provider-agnostic messages to Groq's OpenAI-style format.
    System prompt is prepended as a system message.
    Tool results become role=tool messages with tool_call_id.
    """
    out = [{"role": "system", "content": system_prompt}]

    for msg in messages:
        role = msg["role"]

        if role == "user":
            out.append({"role": "user", "content": msg["content"]})

        elif role == "assistant":
            assistant_msg: dict = {"role": "assistant", "content": msg.get("content") or None}
            # Re-attach tool_calls if this was a tool-use turn
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