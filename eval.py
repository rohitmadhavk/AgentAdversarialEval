"""
eval.py — adversarial evaluation harness.

Phase 1 — Two-prompt A/B comparison (20 cases, normal execution):
    python eval.py

Phase 2 — Fault injection (automatic, one case per tool):
    Runs automatically after Phase 1. One representative happy-path case per
    distinct expected_tool is selected programmatically — all three tools are
    always covered, no manual flags needed.
    Global injection (all tools simultaneously): FORCE_FAIL=manage_tasks,convert_units,get_weather make eval-fail

Reports per system prompt:
  - tool-selection accuracy (happy path)
  - preferred-tool rate    (ambiguous)
  - abstention rate        (out-of-scope)
  - p95 / mean latency

Plus a fault-injection summary:
  - graceful-degradation score (right tool attempted + agent survived)

Results saved to eval_results.json.
"""

import json
import os
import random
import statistics
import time
from dataclasses import dataclass, field

from agent import run_turn
from cases import Case, CASES, FAULT_CASES, MULTI_TURN_CASES
from db import init_db, reset_db
from fault import wrap_tools
from hooks import TimingHook
from llm import get_provider
from prompts import PROMPTS
from scoring import score, score_fault, score_turn
from tools import TOOL_FUNCTIONS

# ── harness ───────────────────────────────────────────────────────────────────

@dataclass
class PromptResult:
    name: str
    rows: list[dict] = field(default_factory=list)
    latencies: list[float] = field(default_factory=list)


def _run_one(
    case: Case,
    system_prompt: str,
    provider,
    idx: int,
    total: int,
    *,
    injecting: bool = False,
) -> dict:
    tag = f"FAULT/{case.expected_tool}" if injecting else case.category[0].upper()
    print(f"  [{idx:02d}/{total}] Case {case.id:02d} [{tag}] {case.prompt[:52]}…")
    t0 = time.perf_counter()
    tool_timings: list[dict] = []
    try:
        if injecting:
            wrapped_fns = wrap_tools(TOOL_FUNCTIONS, case.expected_tool)
            turn = run_turn(case.prompt, system_prompt, provider=provider,
                            hooks=TimingHook(tool_timings),
                            tool_functions=wrapped_fns)
        else:
            turn = run_turn(case.prompt, system_prompt, provider=provider,
                            hooks=TimingHook(tool_timings))
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        print(f"    ✗ CRASH: {exc}")
        return {
            "case_id": case.id, "category": case.category,
            "expected_tool": case.expected_tool,
            "pass": False, "latency_s": round(elapsed, 3),
            "tools_called": [], "tool_errors": [], "tool_timings": [],
            "response": "", "note": f"CRASH: {exc}",
        }
    elapsed = time.perf_counter() - t0
    net_latency = elapsed - turn.get("backoff_s", 0.0)
    if injecting:
        ok, note = score_fault(case, turn)
    else:
        ok, note = score(case, turn["tools_called"], turn["response"])
    print(f"    {'✓' if ok else '✗'} {note}  ({net_latency:.2f}s net)")
    return {
        "case_id": case.id, "category": case.category,
        "expected_tool": case.expected_tool,
        "pass": ok, "latency_s": round(net_latency, 3),
        "tools_called": turn["tools_called"],
        "tool_errors": turn["tool_errors"],
        "tool_timings": tool_timings,
        "response": turn["response"][:120],
        "note": note,
    }


def run_eval(
    only_case: int | None = None,
    only_prompt: str | None = None,
) -> dict[str, PromptResult]:
    """Phase 1: two-prompt A/B comparison on the full 20-case set.

    Interleaving strategy
    ─────────────────────
    Cases 1–4 form a stateful CRUD chain (add→list→complete→delete) and must
    run as a complete block per prompt before the DB is reset.  They are run
    as block-a then block-b at the start.

    Cases 5–20 are independent and are interleaved: both prompts see case 5
    before either sees case 6, so they share the same external conditions
    (same NWS weather snapshot, same rate-limit window).  This eliminates
    temporal confounders from the A/B comparison.

    Args:
        only_case:   if set, run only the case with this ID (both prompts).
        only_prompt: if set, run only the named prompt variant.
    """
    init_db()
    provider = get_provider()
    prompts_to_run = {
        k: v for k, v in PROMPTS.items()
        if only_prompt is None or k == only_prompt
    }

    results: dict[str, PromptResult] = {n: PromptResult(name=n) for n in prompts_to_run}
    last_case_end: float = 0.0

    def _pace():
        """Adaptive gap: wait until 4s has elapsed since the last case ended."""
        nonlocal last_case_end
        if last_case_end and only_case is None:
            gap = 4.0 - (time.perf_counter() - last_case_end)
            if gap > 0:
                time.sleep(gap)

    def _run_and_record(case: Case, prompt_name: str, system_prompt: str, idx: int, total: int):
        nonlocal last_case_end
        _pace()
        row = _run_one(case, system_prompt, provider, idx, total)
        results[prompt_name].rows.append(row)
        results[prompt_name].latencies.append(row["latency_s"])
        last_case_end = time.perf_counter()

    if only_case is not None:
        # Single-case rerun: run for each prompt in sequence, no pacing.
        case = next(c for c in CASES if c.id == only_case)
        total = 1
        for prompt_name, system_prompt in prompts_to_run.items():
            reset_db()
            _run_and_record(case, prompt_name, system_prompt, 1, total)
        return results

    # ── Full run ──────────────────────────────────────────────────────────────
    # Phase A: run CRUD chain (cases 1–4) as a block for each prompt.
    crud_cases = [c for c in CASES if c.id <= 4]
    for prompt_name, system_prompt in prompts_to_run.items():
        print(f"\n{'='*56}\n  {prompt_name}  [cases 1–4 CRUD block]\n{'='*56}")
        reset_db()
        for i, case in enumerate(crud_cases, 1):
            _run_and_record(case, prompt_name, system_prompt, i, len(crud_cases))

    # Phase B: run cases 5–20 interleaved across prompts.
    # Shuffle order to reduce category clustering; same shuffled order used for both.
    tail_cases = [c for c in CASES if c.id > 4]
    random.shuffle(tail_cases)
    prompt_items = list(prompts_to_run.items())
    total_interleaved = len(tail_cases) * len(prompt_items)
    global_idx = 0
    for case in tail_cases:
        for prompt_name, system_prompt in prompt_items:
            global_idx += 1
            label = f"{prompt_name} | case {case.id}"
            print(f"\n{'='*56}\n  {label}\n{'='*56}")
            _run_and_record(case, prompt_name, system_prompt, global_idx, total_interleaved)

    return results


def run_fault_injection(
    only_prompt: str | None = None,
) -> dict[str, list[dict]]:
    """Phase 2: re-run FAULT_CASES with tool-failure injection for every prompt.

    Returns a dict keyed by prompt name so graceful-degradation is measured
    independently for each agent variant (prompt_a_verbose vs prompt_b_terse).
    """
    if not FAULT_CASES:
        return {}
    provider = get_provider()
    prompts_to_run = {
        k: v for k, v in PROMPTS.items()
        if only_prompt is None or k == only_prompt
    }
    results: dict[str, list[dict]] = {}
    total = len(FAULT_CASES)
    last_case_end: float = 0.0
    for prompt_name, system_prompt in prompts_to_run.items():
        print(f"\n{'='*56}\n  FAULT INJECTION  ({prompt_name})\n{'='*56}")
        reset_db()
        rows: list[dict] = []
        for i, case in enumerate(FAULT_CASES, 1):
            if last_case_end:
                gap = 4.0 - (time.perf_counter() - last_case_end)
                if gap > 0:
                    time.sleep(gap)
            row = _run_one(case, system_prompt, provider, i, total, injecting=True)
            row["injected_tool"] = case.expected_tool
            rows.append(row)
            last_case_end = time.perf_counter()
        results[prompt_name] = rows
    return results


def run_multi_turn_eval(
    only_prompt: str | None = None,
) -> dict[str, list[dict]]:
    """Phase 3: multi-turn eval on MULTI_TURN_CASES for every prompt.

    Each case is a conversation sequence where the correct tool call on turn N
    depends on information produced in turn N-1.  History is carried across
    turns; the DB is reset before each case.

    Returns a dict keyed by prompt name → list of case-level result dicts.
    """
    if not MULTI_TURN_CASES:
        return {}
    provider = get_provider()
    prompts_to_run = {
        k: v for k, v in PROMPTS.items()
        if only_prompt is None or k == only_prompt
    }
    results: dict[str, list[dict]] = {}

    for prompt_name, system_prompt in prompts_to_run.items():
        print(f"\n{'='*56}\n  MULTI-TURN EVAL  ({prompt_name})\n{'='*56}")
        case_rows: list[dict] = []
        for mt_case in MULTI_TURN_CASES:
            reset_db()
            history: list[dict] = []
            turn_rows: list[dict] = []
            case_pass = True
            print(f"\n  Case MT{mt_case.id}: {mt_case.description}")
            for t_idx, turn in enumerate(mt_case.turns, 1):
                print(f"    Turn {t_idx}: {turn.prompt[:60]}…")
                tool_timings: list[dict] = []
                try:
                    result = run_turn(
                        turn.prompt, system_prompt,
                        history=history,
                        provider=provider,
                        hooks=TimingHook(tool_timings),
                    )
                except Exception as exc:
                    ok, note = False, f"CRASH: {exc}"
                    turn_rows.append({
                        "turn": t_idx, "pass": False,
                        "tools_called": [], "response": "", "note": note,
                    })
                    case_pass = False
                    print(f"      ✗ {note}")
                    break

                history = result["messages"]
                ok, note = score_turn(turn, result["tools_called"], result["response"])
                if not ok:
                    case_pass = False
                print(f"      {'✓' if ok else '✗'} {note}")
                turn_rows.append({
                    "turn": t_idx,
                    "pass": ok,
                    "tools_called": result["tools_called"],
                    "response": result["response"][:120],
                    "note": note,
                })

            case_rows.append({
                "case_id": mt_case.id,
                "description": mt_case.description,
                "pass": case_pass,
                "turns": turn_rows,
            })
        results[prompt_name] = case_rows
    return results


# ── reporting ─────────────────────────────────────────────────────────────────

def _p95(lats: list[float]) -> float:
    if not lats:
        return 0.0
    s = sorted(lats)
    idx = max(0, int(len(s) * 0.95) - 1)
    return s[idx]


def print_report(
    results: dict[str, PromptResult],
    fault_rows: dict[str, list[dict]],
    multi_turn_rows: dict[str, list[dict]] | None = None,
) -> None:
    W = 56
    print(f"\n{'='*W}\n  RESULTS SUMMARY\n{'='*W}")
    summary: list[dict] = []

    for name, pr in results.items():
        happy = [r for r in pr.rows if r["category"] == "happy"]
        amb   = [r for r in pr.rows if r["category"] == "ambiguous"]
        oos   = [r for r in pr.rows if r["category"] == "out_of_scope"]
        tool_acc     = sum(r["pass"] for r in happy) / len(happy) if happy else 0.0
        amb_acc      = sum(r["pass"] for r in amb)   / len(amb)   if amb   else 0.0
        abstain_rate = sum(r["pass"] for r in oos)   / len(oos)   if oos   else 0.0
        lats = pr.latencies
        p95  = _p95(lats)
        mean = statistics.mean(lats) if lats else 0.0
        summary.append({"name": name, "tool_acc": tool_acc, "amb_acc": amb_acc,
                         "abstain": abstain_rate, "p95": p95, "mean": mean})

        print(f"\n  ── {name} ──")
        print(f"    Tool accuracy  (happy-path):  {tool_acc:.0%}  ({sum(r['pass'] for r in happy)}/{len(happy)})")
        _tool_names = sorted({r.get("expected_tool", "?") for r in happy})
        for _t in _tool_names:
            _tr = [r for r in happy if r.get("expected_tool") == _t]
            print(f"      {_t:20s}  {sum(r['pass'] for r in _tr)}/{len(_tr)}")
        print(f"    Preferred tool (ambiguous):   {amb_acc:.0%}  ({sum(r['pass'] for r in amb)}/{len(amb)})")
        print(f"    Abstention rate (OOS):        {abstain_rate:.0%}  ({sum(r['pass'] for r in oos)}/{len(oos)})")
        print(f"    p95 latency:                  {p95:.2f}s")
        print(f"    mean latency:                 {mean:.2f}s")
        failures = [r for r in pr.rows if not r["pass"]]
        if failures:
            print(f"    Failures ({len(failures)}):")
            for f in failures:
                print(f"      Case {f['case_id']:02d} [{f['category'][0].upper()}]: {f['note']}")

    # Fault injection summary — one block per prompt
    if fault_rows:
        print(f"\n  ── Fault injection ──")
        for prompt_name, rows in fault_rows.items():
            survived = sum(r["pass"] for r in rows)
            tools_covered = sorted({r.get("injected_tool", "?") for r in rows})
            print(f"    {prompt_name}  ({len(rows)} case(s), tools: {', '.join(tools_covered)})")
            print(f"      Graceful degradation:       {survived}/{len(rows)}")
            for r in rows:
                print(f"        Case {r['case_id']:02d} [{r.get('injected_tool', '?')}]: {r['note']}")

    # Multi-turn summary
    if multi_turn_rows:
        print(f"\n  ── Multi-turn eval ──")
        for prompt_name, cases in multi_turn_rows.items():
            passed = sum(c["pass"] for c in cases)
            print(f"    {prompt_name}:  {passed}/{len(cases)} cases passed")
            for c in cases:
                mark = "✓" if c["pass"] else "✗"
                print(f"      {mark} MT{c['case_id']}: {c['description']}")
                for t in c["turns"]:
                    tm = "✓" if t["pass"] else "✗"
                    print(f"          Turn {t['turn']} {tm}  {t['note']}")

    # Persist results — merge into existing JSON so partial runs patch individual rows
    out_path = "eval_results.json"
    try:
        with open(out_path) as fh:
            existing: dict = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        existing = {}

    for name, pr in results.items():
        prev_rows: list[dict] = existing.get(name, [])
        new_by_id = {r["case_id"]: r for r in pr.rows}
        merged = {r["case_id"]: r for r in prev_rows}
        merged.update(new_by_id)
        existing[name] = [merged[k] for k in sorted(merged)]

    if fault_rows:
        existing["fault_injection"] = fault_rows  # dict keyed by prompt name

    if multi_turn_rows:
        existing["multi_turn"] = multi_turn_rows

    with open(out_path, "w") as fh:
        json.dump(existing, fh, indent=2)
    print(f"\n  Saved → {out_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Adversarial eval harness")
    parser.add_argument("--case", type=int, default=None,
                        help="Run a single case ID only (e.g. --case 5)")
    parser.add_argument("--prompt", type=str, default=None,
                        help="Run a single prompt variant only (e.g. --prompt prompt_a_verbose)")
    parser.add_argument("--fault-only", action="store_true",
                        help="Skip Phase 1 and run fault injection only")
    parser.add_argument("--multi-turn-only", action="store_true",
                        help="Skip Phase 1/2 and run multi-turn eval only")
    args = parser.parse_args()

    force = os.environ.get("FORCE_FAIL", "")
    if force:
        print(f"⚠  FORCE_FAIL={force} (global injection active)")

    skip_phase1 = args.fault_only or args.multi_turn_only
    if not skip_phase1:
        eval_results = run_eval(only_case=args.case, only_prompt=args.prompt)
    else:
        eval_results = {}

    fault_results = (
        run_fault_injection(only_prompt=args.prompt)
        if not args.case and not args.multi_turn_only
        else {}
    )
    multi_turn_results = (
        run_multi_turn_eval(only_prompt=args.prompt)
        if not args.case and not args.fault_only
        else {}
    )
    print_report(eval_results, fault_results, multi_turn_results)