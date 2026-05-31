"""
fault.py — fault injection infrastructure for the eval harness.

Kept separate from tools.py so production tool code carries no knowledge
of test infrastructure (DIP: test infra depends on production, never reverse).

Usage (eval harness only):

    from fault import wrap_tools
    from tools import TOOL_FUNCTIONS

    wrapped = wrap_tools(TOOL_FUNCTIONS, "convert_units")
    turn = run_turn(..., tool_functions=wrapped)

FORCE_FAIL env var for CLI injection (full function names):
    FORCE_FAIL=manage_tasks,get_weather make eval-fail
"""

import os
from collections.abc import Callable

# Immutable — populated once at import from env var.  Never mutated at runtime.
# Tool names must be exact function names: manage_tasks, convert_units, get_weather.
_FORCE_FAIL: frozenset[str] = frozenset(
    s.strip().lower()
    for s in os.environ.get("FORCE_FAIL", "").split(",")
    if s.strip()
)


def wrap_tools(fn_map: dict[str, Callable], *extra_fail_tools: str) -> dict[str, Callable]:
    """Return a shallow copy of fn_map with named tools replaced by failing wrappers.

    Any tool whose name appears in FORCE_FAIL or extra_fail_tools raises
    RuntimeError when called, simulating an irrecoverable tool failure.
    The original fn_map is never mutated — safe to call repeatedly.

        wrapped = wrap_tools(TOOL_FUNCTIONS, "convert_units")
        run_turn(..., tool_functions=wrapped)

    Args:
        fn_map:           tool name → callable dispatch map
        *extra_fail_tools: additional tool names to fail for this call only
    """
    fail: frozenset[str] = _FORCE_FAIL | frozenset(t.lower() for t in extra_fail_tools)
    result: dict[str, Callable] = {}
    for name, fn in fn_map.items():
        if name.lower() in fail:
            # Default-argument capture avoids the classic late-binding closure trap.
            def _failing(*args, _name: str = name, **kwargs) -> None:
                raise RuntimeError(f"[injected] {_name} tool failed")
            result[name] = _failing
        else:
            result[name] = fn
    return result
