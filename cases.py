"""
cases.py — eval dataset: Case dataclass, all 20 cases, and the derived fault set.

This module only defines *what* to test, not how to run or score it.
Add new cases here without touching harness or scoring logic.
"""

from dataclasses import dataclass


@dataclass
class Case:
    id: int
    category: str       # happy | ambiguous | out_of_scope
    prompt: str
    expected_tool: str  # tool name | "none" | "ambiguous"
    preferred_tool: str
    reason: str = ""    # for ambiguous cases: why preferred_tool wins


CASES: list[Case] = [
    # ── happy path (10) ───────────────────────────────────────────────────
    Case(1,  "happy", "Add 'buy groceries' to my task list.",        "manage_tasks", "manage_tasks"),
    Case(2,  "happy", "Show me all my current tasks.",               "manage_tasks", "manage_tasks"),
    Case(3,  "happy", "Mark task number 1 as complete.",             "manage_tasks", "manage_tasks"),
    Case(4,  "happy", "Delete the first task in my list.",           "manage_tasks", "manage_tasks"),
    Case(5,  "happy", "Convert 100 kilometers to miles.",              "convert_units", "convert_units"),
    Case(6,  "happy", "How many pounds is 75 kilograms?",              "convert_units", "convert_units"),
    Case(7,  "happy", "What is 32 degrees Fahrenheit in Celsius?",     "convert_units", "convert_units"),
    Case(8,  "happy", "What's the weather like in New York right now?",  "get_weather",  "get_weather"),
    Case(9,  "happy", "Is it cold in Chicago today?",                     "get_weather",  "get_weather"),
    Case(10, "happy", "What's the current temperature in Los Angeles?",   "get_weather",  "get_weather"),
    # ── ambiguous (5) ─────────────────────────────────────────────────────
    Case(11, "ambiguous",
         "Should I bring a jacket to my meeting in Miami today?",
         "ambiguous", "get_weather",
         reason="Weather is the root question; the jacket is just context."),
    Case(12, "ambiguous",
         "I need to remember to check the weather in Seattle before I leave.",
         "ambiguous", "manage_tasks",
         reason="Explicit reminder intent — user wants a to-do entry, not a forecast."),
    Case(13, "ambiguous",
         "Convert the temperature in Boston right now to Celsius.",
         "ambiguous", "get_weather",
         reason="No numeric value is in the conversation — get_weather must run first to fetch the current temperature; convert_units requires a known input value."),
    Case(14, "ambiguous",
         "Add a task to check if it's going to rain in Houston this weekend.",
         "ambiguous", "manage_tasks",
         reason="'Add a task' is an explicit store-a-reminder instruction."),
    Case(15, "ambiguous",
         "The forecast says Seattle is 28 degrees Celsius today — what is that in Fahrenheit?",
         "ambiguous", "convert_units",
         reason="The numeric value (28°C) is already in the prompt — convert_units can run immediately; fetching weather would be redundant since the temperature is already known."),
    # ── out-of-scope (5) ──────────────────────────────────────────────────
    # 16-17: obviously OOS — no tool is remotely relevant
    Case(16, "out_of_scope", "Write me a poem about autumn leaves.",           "none", "none"),
    Case(17, "out_of_scope", "What is the capital of Australia?",              "none", "none"),
    # 18: in-domain (weather) but historical — tool only returns current conditions
    Case(18, "out_of_scope", "What was the weather like in Chicago last Tuesday?", "none", "none"),
    # 19: sounds like convert units but requires a live data lookup, not arithmetic
    Case(19, "out_of_scope", "What's the current USD to EUR exchange rate?",   "none", "none"),
    # 20: in-domain (weather) but out-of-capability — Cairo is not a supported city
    Case(20, "out_of_scope", "What's the weather like in Cairo right now?",    "none", "none"),
]

# Derive fault cases: one representative per distinct expected_tool from happy-path.
# Self-maintaining — adding a fourth tool to the dataset adds a fourth fault case
# automatically, with no manual flagging required.
_seen: set[str] = set()
FAULT_CASES: list[Case] = []
for _c in CASES:
    if _c.category == "happy" and _c.expected_tool not in _seen:
        FAULT_CASES.append(_c)
        _seen.add(_c.expected_tool)
del _seen
