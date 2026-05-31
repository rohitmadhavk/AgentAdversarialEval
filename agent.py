"""
agent.py — tool-agnostic agent loop.

    python agent.py                        # interactive
    FORCE_FAIL=manage_tasks python agent.py  # with injected failure
"""

import json
import time
from llm import get_provider, LLMProvider
from hooks import Hook
from tools import TOOL_SCHEMAS as _DEFAULT_TOOL_SCHEMAS, TOOL_FUNCTIONS as _DEFAULT_TOOL_FUNCTIONS

MAX_ROUNDS = 5


def run_turn(
    user_message: str,
    system_prompt: str,
    history: list[dict] | None = None,
    provider: LLMProvider | None = None,
    hooks: Hook | None = None,
    tool_schemas: list[dict] | None = None,
    tool_functions: dict | None = None,
) -> dict:
    """Run a single agent turn.

    Args:
        user_message:   the user's input for this turn
        system_prompt:  system instruction string
        history:        prior message history (mutated copy used internally)
        provider:       LLMProvider to use; defaults to get_provider()
        hooks:          Hook callbacks for logging/timing/tracing
        tool_schemas:   overrides the default TOOL_SCHEMAS (e.g. for testing)
        tool_functions: overrides the default TOOL_FUNCTIONS (e.g. fault injection)
    """
    if provider is None:
        provider = get_provider()
    if hooks is None:
        hooks = Hook()
    if tool_schemas is None:
        tool_schemas = _DEFAULT_TOOL_SCHEMAS
    if tool_functions is None:
        tool_functions = _DEFAULT_TOOL_FUNCTIONS

    messages = list(history or [])
    messages.append({"role": "user", "content": user_message})

    tools_called: list[str] = []
    tool_errors:  list[tuple[str, str]] = []
    final_text = None
    total_backoff_s = 0.0
    t_turn_start = time.perf_counter()

    for _ in range(MAX_ROUNDS):
        response = provider.complete(messages, system_prompt, tool_schemas)
        total_backoff_s += response.backoff_s

        if response.text:
            final_text = response.text

        if response.stop_reason != "tool_use" or not response.tool_calls:
            break

        messages.append({
            "role": "assistant",
            "content": response.text or "",
            "_tool_calls": [{"id": tc.id, "name": tc.name, "input": tc.input} for tc in response.tool_calls],
        })

        for tc in response.tool_calls:
            tools_called.append(tc.name)
            hooks.on_tool_call(tc.name, tc.input)
            t0 = time.perf_counter()
            try:
                result = tool_functions[tc.name](**tc.input)
                content = json.dumps(result)
                hooks.on_tool_result(tc.name, result, time.perf_counter() - t0)
            except KeyError:
                msg = f"unknown tool '{tc.name}'"
                exc = KeyError(msg)
                tool_errors.append((tc.name, msg))
                hooks.on_tool_error(tc.name, exc)
                content = json.dumps({"error": msg})
            except Exception as exc:
                tool_errors.append((tc.name, str(exc)))
                hooks.on_tool_error(tc.name, exc)
                content = json.dumps({"error": str(exc)})

            messages.append({"role": "tool", "tool_use_id": tc.id, "name": tc.name, "content": content})
            

    hooks.on_turn_end(tools_called, time.perf_counter() - t_turn_start)
    return {
        "response":     final_text or "(no response)",
        "tools_called": tools_called,
        "tool_errors":  tool_errors,
        "messages":     messages,
        "backoff_s":    total_backoff_s,
    }


def main():
    from prompts import PROMPT_A, PROMPT_B, PROMPT_C
    from db import init_db
    init_db()

    provider = get_provider()
    print(f"Agent [{provider.name}] ready. 'quit' to exit.\n")
    history: list[dict] = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input or user_input.lower() in {"quit", "exit"}:
            break

        result = run_turn(user_input, PROMPT_A, history, provider)
        print(f"\nAgent: {result['response']}")
        if result["tools_called"]:
            print(f"  [tools: {', '.join(result['tools_called'])}]")
        if result["tool_errors"]:
            for name, err in result["tool_errors"]:
                print(f"  [error — {name}: {err}]")
        print()
        history = result["messages"]


if __name__ == "__main__":
    main()