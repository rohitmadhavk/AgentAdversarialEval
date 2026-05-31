"""
hooks.py — middleware for the agent loop.

A Hook is a dataclass with optional callbacks that fire at key points
in run_turn(). Pass one to run_turn() to get logging, timing, cost
tracking, or anything else without touching the agent loop itself.

    from hooks import Hook, LoggingHook

    result = run_turn(msg, prompt, hooks=LoggingHook())

Production extensions that would live here:
  - cost tracking (input/output tokens per call)
  - retry with exponential backoff on tool failure
  - distributed tracing (emit spans to OpenTelemetry)
  - rate-limit enforcement
"""

import time
from dataclasses import dataclass, field
from typing import Callable, Any


@dataclass
class Hook:
    """
    Base hook — all callbacks are no-ops by default.
    Subclass and override only what you need.
    """
    on_tool_call:   Callable[[str, dict], None]           = field(default=lambda name, args: None)
    on_tool_result: Callable[[str, dict, float], None]    = field(default=lambda name, result, elapsed: None)
    on_tool_error:  Callable[[str, Exception], None]      = field(default=lambda name, exc: None)
    on_turn_end:    Callable[[list[str], float], None]    = field(default=lambda tools, elapsed: None)


def LoggingHook() -> Hook:
    """Ready-made hook that prints a structured trace of every tool call."""
    def _call(name: str, args: dict):
        print(f"  → {name}({', '.join(f'{k}={v!r}' for k, v in args.items())})")

    def _result(name: str, result: dict, elapsed: float):
        status = "error" if "error" in result else "ok"
        print(f"  ← {name} [{status}] {elapsed*1000:.0f}ms")

    def _error(name: str, exc: Exception):
        print(f"  ✗ {name} raised: {exc}")

    def _end(tools: list[str], elapsed: float):
        print(f"  turn complete — {len(tools)} tool call(s), {elapsed:.2f}s total")

    return Hook(
        on_tool_call=_call,
        on_tool_result=_result,
        on_tool_error=_error,
        on_turn_end=_end,
    )


def TimingHook(store: list) -> Hook:
    """
    Collects per-tool latency into `store` for the eval harness.
    store is a list that receives dicts: {tool, latency_ms, error}.
    """
    def _call(name: str, args: dict):
        store.append({"tool": name, "_t0": time.perf_counter()})

    def _result(name: str, result: dict, elapsed: float):
        if store and store[-1]["tool"] == name:
            store[-1]["latency_ms"] = round(elapsed * 1000, 1)
            store[-1]["error"] = "error" in result
            store[-1].pop("_t0", None)

    def _error(name: str, exc: Exception):
        if store and store[-1]["tool"] == name:
            store[-1]["latency_ms"] = -1
            store[-1]["error"] = True
            store[-1]["exc"] = str(exc)
            store[-1].pop("_t0", None)

    return Hook(on_tool_call=_call, on_tool_result=_result, on_tool_error=_error)