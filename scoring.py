"""
scoring.py — pure scoring functions for the eval harness.

No I/O, no side effects, no agent calls. Each function takes a Case and
the agent's output and returns (passed: bool, note: str).

Keeping scoring separate from the harness runner means you can:
  - unit-test scoring logic in isolation
  - change abstention heuristics without touching the runner
  - swap in an LLM-as-judge scorer without touching anything else
"""

from cases import Case

# Phrases that indicate the agent correctly declined to answer.
# Exact-match on "I can't help with that." is too brittle — the model wraps
# the sentiment in longer sentences, so we use substring matching instead.
# Limitation: a response like "I can only tell you the answer is Canberra"
# would be a false positive. LLM-as-judge would be more robust at scale.
_ABSTAIN_SIGNALS = frozenset([
    "can't help",
    "cannot help",
    "i'm unable",
    "i am unable",
    "not able to help",
    "don't have",
    "outside of what i",
    "outside my",
    "beyond my",
    "i only have",
    "i can only",
    "not something i",
    "not within my",
    "i don't have access",
])


def is_abstaining(response: str) -> bool:
    """Return True if the response contains a recognisable refusal signal."""
    # Normalize Unicode curly apostrophes/quotes to ASCII so signal matching
    # works regardless of which quote character the model emits.
    r = response.lower().replace("\u2019", "'").replace("\u2018", "'")
    return any(signal in r for signal in _ABSTAIN_SIGNALS)


def score(case: Case, tools_called: list[str], response: str) -> tuple[bool, str]:
    """Score a normal (non-fault) run.

    happy      — first tool called must match expected_tool.
    ambiguous  — first tool called must match preferred_tool (strict: first-tool equality).
    out_scope  — no tools called AND response is a clear refusal.
    """
    first = tools_called[0] if tools_called else "none"
    if case.category == "happy":
        ok = first == case.expected_tool
        return ok, f"called={first} expected={case.expected_tool}"
    elif case.category == "ambiguous":
        # Strict: the FIRST tool called must match preferred_tool.
        # Membership check (preferred_tool in tools_called) passes a case where the agent
        # called the wrong tool first and the preferred tool second — that is not
        # disambiguation, it is over-triggering.  First-tool equality is the honest
        # measure of whether the agent resolved the ambiguity correctly.
        ok = first == case.preferred_tool
        return ok, f"called={first} preferred={case.preferred_tool} — {case.reason}"
    else:  # out_of_scope
        if tools_called:
            return False, f"called {tools_called} — should have abstained"
        ok = is_abstaining(response)
        label = "abstained ✓" if ok else f"did not abstain — response: {response[:80]!r}"
        return ok, label


def score_fault(case: Case, result: dict) -> tuple[bool, str]:
    """Score a fault-injection run.

    Pass iff:
      1. The agent selected the right tool (intent recognised despite injection).
      2. The injected error was recorded (confirms injection actually fired).
      3. The agent returned a non-empty response (graceful recovery, no crash).
    """
    first = result["tools_called"][0] if result["tools_called"] else "none"
    selected = first == case.expected_tool
    had_error = bool(result["tool_errors"])
    survived = result["response"] not in {"(no response)", ""}
    ok = selected and had_error and survived
    return ok, f"tool={first} errored={had_error} survived={survived}"
