# Agent Adversarial Eval

Assignment 2 — Agent, Adversarial Eval.

## Contents

1. [Why This Assignment](#why-this-assignment)
2. [Architecture](#architecture)
3. [Evaluation Design](#evaluation-design)
   - [10/5/5 Prompt Split](#1055-prompt-split)
   - [Three System Prompts](#three-system-prompts)
   - [Fault Injection](#fault-injection)
4. [Headline Numbers](#headline-numbers)
   - [Phase 1 — Three-prompt comparison](#phase-1--three-prompt-comparison)
   - [Phase 2 — Fault Injection](#phase-2--fault-injection)
5. [Failure Mode](#failure-mode)
6. [Decisions and Alternatives](#decisions-and-alternatives)
7. [What I Would Do Differently With Another Week](#what-i-would-do-differently-with-another-week)
8. [Reproducing](#reproducing)
9. [File Map](#file-map)

## Why This Assignment

Assignment 2 has the sharpest signal-to-noise ratio for demonstrating real engineering judgment. The 10/5/5 prompt split (happy / ambiguous / out-of-scope) forces you to make a defensible argument for each ambiguous case rather than just running a benchmark. The three-prompt comparison isolates controlled variables — verbosity and framing polarity — and produces a dimension-by-dimension winner table. And the fault-injection requirement means you have to deliberately break the system and prove it recovers, not just show it working under ideal conditions.

The mandatory failure mode section is what makes this different from a tutorial: you cannot fake it without running the experiments.

## Architecture

Three tools, meaningfully different in kind:

| Tool | Type | Description |
|------|------|-------------|
| `manage_tasks` | **Stateful** (SQLite) | Add, list, complete, delete items in a persistent to-do list |
| `convert_units` | Stateless | Convert values between units — temperature, distance, mass, volume, speed |
| `get_weather` | Stateless, HTTP | Fetch live weather from [NWS API](https://api.weather.gov) for 10 US cities |

The agent loop (`agent.py`) is tool-agnostic. It calls the LLM, dispatches whatever tool calls come back, feeds results into the message history, and loops until `stop_reason != "tool_use"` or `MAX_ROUNDS` is reached. There are no hand-coded routing `if`-statements. Tool selection is driven entirely by LLM inference over the schemas in `TOOL_SCHEMAS`.

### Provider abstraction

`llm/base_provider.py` defines a `LLMProvider` interface. Three providers implement it — `GroqProvider`, `GeminiProvider`, and `NvidiaProvider` — all translating the same internal message format and tool schemas to their respective APIs. Swapping providers requires one line in `llm/__init__.py`.

This abstraction was stress-tested under real conditions rather than just designed for it. Groq's 100k daily token quota was exhausted mid-run after prompt_a completed; switching to Gemini required one line change and zero harness edits. Gemini's 15 RPM free-tier limit was then hit at case 12 (case 4 alone makes 5 tool calls, burning through the window faster than case count suggests); a further one-line switch to NVIDIA NIM resolved it. All three providers ran the same 20 cases against the same schemas — the abstraction held across three different API formats and authentication schemes.

Each provider implementation includes exponential backoff for 429 rate-limit responses. NVIDIA NIM's backoff schedule (`20s → 45s → 65s`) is tuned so the third retry always fires after the 60-second rolling window resets — eliminating cascading failures where a burst in one case causes all subsequent cases to fail.

### Stateful tool

`manage_tasks` reads and writes a SQLite database (`tasks.db`) across turns. The eval harness calls `reset_db()` before each prompt run — which deletes all rows **and** resets the autoincrement sequence — so task IDs restart from 1 and delete/complete calls referencing specific IDs behave identically across runs.

## Evaluation Design

### 10/5/5 Prompt Split

**Happy path (10 cases)** — each maps unambiguously to exactly one tool (3–4 cases per tool). A case passes if the first tool called matches `expected_tool`.

**Ambiguous (5 cases)** — each prompt could plausibly invoke two tools. For each I recorded a `preferred_tool` and the reasoning:

| Case | Prompt (abbreviated) | Preferred | Why |
|------|----------------------|-----------|-----|
| 11 | "Should I bring a jacket to Miami today?" | `get_weather` | Weather is the root question; the jacket is just framing |
| 12 | "I need to remember to check the weather in Seattle before I leave" | `manage_tasks` | Explicit reminder intent — user wants a to-do entry, not a forecast |
| 13 | "Convert the temperature in Boston right now to Celsius" | `get_weather` | No numeric value is in the conversation — `get_weather` must run first; `convert_units` requires a known input value |
| 14 | "Add a task to check if it's going to rain in Houston this weekend" | `manage_tasks` | "Add a task" is an unambiguous instruction to store a reminder |
| 15 | "The forecast says Seattle is 28°C today — what is that in Fahrenheit?" | `convert_units` | The numeric value (28°C) is already in the prompt — `convert_units` can run immediately; fetching weather would be redundant |

**Out-of-scope (5 cases)** — four are fully out-of-domain (creative writing, general knowledge, translation, sports results). The fifth, case 20, is deliberately **in-domain but out-of-capability**: *"What's the weather like in Cairo right now?"* The agent supports weather queries, but only for 10 US cities — Cairo is not in the list. A correct agent reads the tool schema, recognises Cairo isn't a supported city, and declines without calling the tool. Calling `get_weather("Cairo")` scores as a fail even though the tool would return a clean error — the agent should refuse *before* the call, not after. This tests schema literacy specifically, not just domain routing.

### Three System Prompts

The three prompts test two axes simultaneously: **verbosity** (prompt_a vs prompt_b) and **framing polarity** (prohibitive "only call when" vs affirmative "use this for any").

**`prompt_a_verbose`** — each tool gets a full description including explicit preconditions: `convert_units` names its unit categories and states *"only call this when a numeric value is already present in the conversation"*; `get_weather` lists its supported cities and says *"decline all others"*. The model has everything it needs to apply constraints without reading the schema.  
Hypothesis: higher accuracy on cases that require reading preconditions (Cases 13, 15, 20); marginal latency cost from larger context.

**`prompt_b_terse`** — each tool gets a one-line description. Preconditions are not restated; the model must infer them from the tool schema. Same rules, fewer words.  
Hypothesis: identical accuracy if the model reads the schema; lower p95 latency from smaller context. This tests whether per-tool preconditions in the system prompt are load-bearing or redundant on a capable model.

**`prompt_c_positive`** — same depth as prompt_a but reframes tool scope with affirmative language: *"Use this for ANY question whose answer requires current weather data"* instead of *"only use this for…"*. Tests whether prohibitive framing suppresses correct tool calls on lifestyle-framed queries where the model may be primed to treat them as Out Of Scope.

### Fault Injection

The harness programmatically injects failures using a context manager (`fault_injector`) — not environment variables, not per-case flags. It derives the fault-test set dynamically: one representative happy-path case per distinct `expected_tool`. This guarantees all three tools are covered regardless of how many cases are in the dataset. Adding a fourth tool to `CASES` automatically adds a fourth fault case.

Pass criteria for a fault case: (1) agent selected the correct tool (intent recognised despite injection), (2) the error was recorded in `tool_errors`, (3) agent returned a non-empty response (graceful recovery, no crash).

## Headline Numbers

> All results use Groq's free tier with `openai/gpt-oss-120b` (OpenAI's open-sourced 120B model running on Groq LPUs). p95 latency ranges from 0.89s (prompt_b) to 1.36s (prompt_a) — genuine model latency, not backoff artefacts. No 429s were encountered during this run.
>
> The provider abstraction (`llm/__init__.py`, one-line swap) was exercised under real conditions across four provider/model combinations before settling here. The checkpoint/resume eval (`--case`, `--prompt`, merge-on-write JSON) was necessary on every provider switch to avoid re-spending quota on already-completed cases. Provider switching history is documented in Decisions and Alternatives.

Run `make run` to reproduce. All results below are from a complete run on Groq (`openai/gpt-oss-120b`).

Latency figures reflect actual model + HTTP round-trip time. No 429s were encountered; the figures are genuine inference latency on Groq LPUs.

### Phase 1 — Three-prompt comparison

| Metric | `prompt_a_verbose` | `prompt_b_terse` | `prompt_c_positive` | Winner |
|--------|-------------------|-----------------|---------------------|--------|
| Tool accuracy — happy path | **10/10 = 100%** | 9/10 = 90% | **10/10 = 100%** | `prompt_a`, `prompt_c` |
| Preferred tool — ambiguous | **5/5 = 100%** | **5/5 = 100%** | **5/5 = 100%** | Tie |
| Abstention — out-of-scope | **5/5 = 100%** | **5/5 = 100%** | **5/5 = 100%** | Tie |
| p95 latency | 1.36 s | 0.89 s | **1.22 s** | `prompt_b` |
| Mean latency | 0.68 s | **0.55 s** | 0.57 s | `prompt_b` |

*prompt_a and prompt_c pass all 20 cases. prompt_b fails Case 4.*

### Head-to-head analysis

**Accuracy: prompt_a and prompt_c pass all 20 cases; prompt_b fails Case 4.** The failure is diagnostic: *"Delete the first task in my list"* requires two sequential `manage_tasks` calls — list to discover the ID, then delete. prompt_b called zero tools and returned a clarifying question asking the user to supply the task ID directly (`tools_called: []`, response: *"I'm not sure which task ID corresponds to the first item in your list…"*) rather than calling `manage_tasks(action="list")` to discover it. All three prompts share an equivalent disambiguation rule (pick one tool when two apply); that rule governs tool *selection* between different tools, not sequential calls to the same tool. The failure is attributable to terseness: prompt_b's one-line description gives the model insufficient signal that the list→delete sequence is needed for a positional delete. prompt_a's explicit preconditions and prompt_c's affirmative framing both guide the model to the correct two-call sequence.

**Case 11 — fixed by correcting the dataset.** The original wording was *"Should I bring a jacket to Miami tomorrow?"*. Both prompts refused rather than calling `get_weather`. The root cause was a dataset design error: `get_weather` returns current conditions only, so a question about tomorrow was labelled `expected_tool = get_weather` — but refusing *was the correct behaviour*. The case was corrected to *"today"*, making the preferred tool genuinely achievable. All three prompts pass the corrected Case 11. The failure mode itself (lifestyle framing masking weather intent) was separately stress-tested and is documented in the Failure Mode section below.

**Case 4 — prompt_b fails; prompt_a and prompt_c pass.** In a previous prompt design, prompt_a contained a *"Call only one tool"* rule which also broke Case 4 by forbidding the list→delete sequence. Removing that rule fixed prompt_a. prompt_b's current failure is different in kind: the terse description gives the model no signal that deleting by position requires a prior list call. prompt_c's affirmative framing (*"Use this for ANY task management operation"*) provides enough context for the model to reason through the sequence without explicit preconditions.

**OOS 5/5 including Case 20 (Cairo).** The model reads the schema's city list and abstains without attempting the tool call. On NVIDIA NIM (`llama-3.3-70b-instruct`) in an earlier run, prompt_a's explicit city instruction caused the model to attempt the call anyway — the verbose instruction overrode schema literacy on that model. The fix was a model change, not a prompt change.

**Latency: prompt_b wins on both p95 and mean, but it also has the only accuracy failure.** prompt_b's p95 (0.89s) and mean (0.55s) are the lowest of the three — fewer prompt tokens genuinely reduce inference time at this context size. But this comes at the cost of Case 4. prompt_a has the highest latency (p95 1.36s, mean 0.68s) driven by Case 4's double `manage_tasks` call (1.38s). prompt_c sits between them (p95 1.22s, mean 0.57s).

**Fault injection: all three prompts survive, but prompt_c's error messaging is misleading.** All nine fault cases (3 tools × 3 prompts) passed the harness — every prompt called each failing tool exactly once and returned a non-empty response. However, prompt_c's `get_weather` fault case returned `"I can't help with that."` — the same string as a correct OOS abstention. The user cannot distinguish a tool failure from an out-of-scope refusal. prompt_a and prompt_b both return explicit error messages (`"The weather lookup failed"`, `"Error: get_weather tool failed."`). This is not a benchmark failure — the spec's bar is survival, and prompt_c survived. But it is a production concern. See Failure Mode section.

### Phase 2 — Fault Injection

Fault injection runs for all three prompts — 3 cases × 3 prompts = 9 total. Pass = right tool attempted + agent survived without crashing.

| Prompt | Tool | Tool called | Error recorded | Survived | Response |
|--------|------|------------|---------------|----------|----------|
| `prompt_a` | `manage_tasks` | ✓ | ✓ | ✓ | "The task could not be added because the manage_tasks tool failed." |
| `prompt_a` | `convert_units` | ✓ | ✓ | ✓ | "The conversion request couldn't be processed — conversion tool returned an error." |
| `prompt_a` | `get_weather` | ✓ | ✓ | ✓ | "The weather lookup failed with an error. Unable to provide current New York weather." |
| `prompt_b` | `manage_tasks` | ✓ | ✓ | ✓ | "Error adding task: [injected] manage_tasks tool failed." |
| `prompt_b` | `convert_units` | ✓ | ✓ | ✓ | "The conversion tool returned an error: [injected] convert_units tool failed." |
| `prompt_b` | `get_weather` | ✓ | ✓ | ✓ | "Error: get_weather tool failed." |
| `prompt_c` | `manage_tasks` | ✓ | ✓ | ✓ | "Error: [injected] manage_tasks tool failed" |
| `prompt_c` | `convert_units` | ✓ | ✓ | ✓ | "The conversion tool returned an error: [injected] convert_units tool failed." |
| `prompt_c` | `get_weather` | ✓ | ✓ | ✓ | "I can't help with that." ⚠ (OOS-style — see Failure Mode) |

Graceful degradation: **9/9** by spec criteria (right tool called, error recorded, non-empty response returned). Caveat: prompt_c's `get_weather` row is a spec pass but a semantic failure — `"I can't help with that."` is indistinguishable from a correct OOS abstention. The scorer cannot tell the difference; a human can. See Failure Mode section for root cause and the LLM-as-judge fix.

## Failure Mode

**Fault error swallowed as OOS abstention — `prompt_c_positive`, Case 08.** Under fault injection, `get_weather` raises a `RuntimeError`. prompt_c called the tool correctly, received the error, and returned:

> *"I can't help with that."*

This is identical to a correct OOS abstention (e.g. Case 20, Cairo). The user cannot tell whether the request was out of scope or whether a tool failed. prompt_a and prompt_b both return explicit error messages under the same conditions (`"The weather lookup failed"`, `"Error: get_weather tool failed."`). 

This is not a benchmark failure — the spec's graceful-degradation bar is survival, and prompt_c survived. All 9/9 fault cases pass. But it is a production failure: silent tool errors cause users to stop asking rather than retry or escalate, and no monitoring signal distinguishes the two outcomes. This is the concrete finding that drove the ship recommendation to prompt_a over prompt_c, and that motivates the LLM-as-judge item in "What I'd do differently."

**Root cause:** prompt_c *does* include an explicit fault-reporting instruction — *"If a tool returns an error, report it plainly and stop. Do not retry."* — identical in intent to prompt_a's. The model received the instruction and ignored it. The mechanism: prompt_c's affirmative scope framing (*"Use this for ANY question whose answer requires current weather data"*) appears to prime the model to treat the `{"error": "..."}` tool response as evidence that the request is out of scope, routing to the OOS refusal path rather than the fault-reporting path. The explicit error-reporting rule is present in context but overridden by framing-driven inference: *"the tool said it can't help → this must not be a question the tool answers → I can't help with that."* This is a more dangerous finding than a missing instruction: affirmative scope framing can silently suppress an explicitly stated rule, and the presence of the rule provides no guarantee it will fire under fault conditions.

**Scorer blind spot:** The substring heuristic cannot distinguish `"I can't help with that"` as a correct OOS refusal from `"I can't help with that"` as a swallowed tool error. Both pass the current harness. An LLM-as-judge step asking *"did the agent correctly explain why it couldn't fulfil this request?"* would catch this; the current harness does not.

---

**Lifestyle framing masks weather intent (development-phase finding).** During development, *"Should I bring a jacket to Miami tomorrow?"* caused both prompts to refuse rather than call `get_weather`. Closer inspection revealed this was a dataset design error: `get_weather` returns current conditions only, so refusing a *tomorrow* question was actually correct behaviour. The case was corrected to *"today"*, which all three prompts pass.

The underlying failure mode — lifestyle framing suppressing correct tool selection — remains real and was stress-tested on the corrected phrasing. A chain-of-thought instruction did not resolve it: the model verbalises *"the user wants to know if they should bring a jacket"*, inheriting the same framing rather than reframing to weather-as-root-intent. The CoT step executes but the misclassification happens inside it. This is a model phrasing-interpretation limit, not a prompt-logic gap.

Eleven failure modes were observed in total across all provider/model combinations during development. Full documentation is in [docs/ANALYSIS.md](docs/ANALYSIS.md).



## Decisions and Alternatives

### Ship prompt decision

**CHOICE:`prompt_a_verbose`.** 

**REASONING**: prompt_b failed Case 4 — the model called zero tools and asked the user to supply the task ID directly (`tools_called: []`), rather than calling `manage_tasks(action="list")` to discover it. The failure is attributable to terseness: the one-line description gives no signal that positional deletes require a prior list call. prompt_c passed Case 4 but failed under fault injection in a different way: when `get_weather` errored, it returned `"I can't help with that."` — indistinguishable from a correct OOS abstention. The user has no way to know whether the request was out of scope or whether a tool failed. This is not a benchmark failure (the spec's graceful-degradation bar is survival, not error transparency), but it is a production failure. prompt_a's verbose fault-reporting instruction produces `"The weather lookup failed — unable to provide current conditions."` — the user knows *why* they got no answer. Between the only two prompts that pass all 20 cases, prompt_a is the safer production choice: preconditions are load-bearing for multi-step stateful operations, and fault messaging is explicit rather than ambiguous.

**Provider selection — evaluated three providers under real conditions:**

| Provider | Limit hit | Cases completed | Outcome |
|---|---|---|---|
| Groq `llama-3.3-70b-versatile` | 100k TPD exhausted | prompt_a: 20/20 | Switched |
| Gemini `gemini-flash-lite` | 15 RPM (case 4 = 5 calls) | 11/20 | Switched |
| NVIDIA NIM `llama-3.3-70b-instruct` | 40 RPM, 1000 RPD | Full run | Switched |
| Groq `openai/gpt-oss-120b` | Free tier, no 429s observed | Full run × 2 | **Active** |

NVIDIA NIM was the right choice among the first three options — the RPD limit is 10× Groq's initial quota, the RPM limit is generous enough that even case 4's 5-call burst doesn't exhaust it, and `llama-3.3-70b-instruct` is the same model family as Groq's `llama-3.3-70b-versatile` so results are directly comparable. The final switch to Groq `openai/gpt-oss-120b` was for latency: Groq's LPU architecture gives genuine sub-second per-call inference that no other free tier matches, and the eval makes ~60 LLM calls across the full run — that compounds. `openai/gpt-oss-120b` also produced zero 429s across two full runs on the free tier. The provider abstraction meant each switch required one line in `llm/__init__.py` — this is the concrete payoff of the interface design, not a hypothetical benefit.

**`calculate` → `convert_units` (security + signal quality):** The original `calculate` tool used `eval()` with a stripped `__builtins__` namespace. This is a well-known incomplete sandbox — `().__class__.__bases__[0].__subclasses__()` traversal still gives access to the full class hierarchy. Replacing it with `convert_units` (pure lookup-table, no code execution) eliminates the attack surface entirely. The replacement also produces a richer disambiguation signal: `convert_units` vs `get_weather` requires the model to reason about whether a numeric value is already present in the conversation — a more realistic decision boundary than arithmetic vs weather routing.

**Ambiguous scoring — first-tool equality over membership check:** The original scorer checked `preferred_tool in tools_called` (membership anywhere in the call sequence). This passes a case where the agent calls the wrong tool first and the preferred tool second, which is over-triggering, not disambiguation. Switching to `tools_called[0] == preferred_tool` makes the metric honest: it measures whether the agent committed to the right choice at decision time, not whether it eventually got there. Both prompts still score 5/5, but the over-triggering failures on prompt_b cases 12 and 14 are now surfaced in the response strings rather than hidden by the metric.

**Three-prompt experiment design — controlled variables:** The three prompts share identical rules (disambiguation, OOS refusal, fault reporting) and differ on two dimensions: verbosity (prompt_a vs prompt_b) and framing polarity (prohibitive "only call when" in prompt_a/b vs affirmative "use this for any" in prompt_c). This is the tightest controlled variable set available without removing a correctness-required instruction (the OOS refusal rule and disambiguation rule are both mandated by the assignment spec). The question the comparison answers: *are per-tool preconditions load-bearing, and does framing polarity affect tool selection?* Answer on `openai/gpt-oss-120b`: preconditions are load-bearing for multi-step stateful operations — prompt_b's terse one-liner is insufficient for the list→delete sequence in Case 4, where the correct second call depends on the result of the first. Framing polarity does not independently affect single-tool accuracy; prompt_c scores identically to prompt_a on all 20 cases. Latency differences correlate weakly with prompt length and are dominated by per-case tool-call count.

**SQLite over a JSON flat file:** Atomic transactions, RETURNING clauses, standard library, no serialisation race conditions. Alternative: a plain JSON file is simpler but has no schema enforcement and is unsafe for concurrent writes. The difference matters for stateful eval correctness.

**Substring abstention matching over exact-match:** The original approach checked `response == "I can't help with that."`. Models wrap refusals in varying sentence structures — this exact match would have scored 0% on OOS cases. We replaced it with 14 substring signals (`"can't help"`, `"outside my"`, etc.) which scored 5/5.

**Dynamic `FAULT_CASES` over a per-case `tools_fail` flag:** A flag on the `Case` dataclass is a dataset concern leaking into harness logic, and it required manual maintenance (only 2/3 tools were covered). Deriving the fault set programmatically from the dataset structure is self-maintaining and guarantees systematic coverage.

**Adversarial schema design over safe schemas:** The tool descriptions were written to stress the model's reasoning rather than make selection trivially easy. `convert_units` says *"only call this when the numeric value is already present in the conversation"* — not a blacklist of forbidden topics. `get_weather` names its 10 supported cities explicitly and prohibits historical queries. The OOS set includes a historical weather query (Case 18 — in-domain but temporally out-of-capability), a financial lookup that superficially resembles a unit conversion (Case 19 — tests whether the model infers that the value itself is the unknown), and an unsupported-city weather query (Case 20 — tests schema literacy directly). Each is designed to fail in a distinct way: capability boundary, number availability, and city coverage respectively. A schema that makes the right answer obvious measures prompt-reading, not reasoning. Harder schemas produce more informative signal — and expose exactly the model behaviours worth documenting.

## What I Would Do Differently With Another Week

**Multi-turn evaluation.** Every case in this harness is a single-turn conversation. A real agent needs to handle stateful sequences: "add a task", then "mark the first one complete", then "list all pending tasks" — where the correct tool call depends on what happened two turns ago. The ambiguous cases in particular would be more revealing in a multi-turn context. This is the highest-value addition.

**LLM-as-judge scoring for abstention and fault responses.** The substring heuristic has two blind spots revealed by this run. First, it cannot distinguish a correct OOS refusal from a misclassified tool failure — prompt_c's fault injection Case 08 returns `"I can't help with that."` after `get_weather` errors, which the harness scores as a pass because the string is non-empty and the tool was called. A judge prompt asking *"did the agent correctly explain why it couldn't fulfil this request?"* would catch this. Second, the heuristic would fail on adversarial inputs like *"I can only help with weather topics, but the capital of Australia is Canberra."* Both failures are the same root cause: substring matching measures surface form, not intent. A single cheap API call per case fixes both.

**Run the same three prompts across multiple model tiers.** The most interesting unanswered question from this eval is: *at what model capability level do prompt differences start to matter?* All three prompts saturate this eval on `openai/gpt-oss-120b`. The provider abstraction is already built — `llm/__init__.py`, one-line swap. The immediate next experiment is to run the same 20 cases against `llama-3.3-70b`, `llama-3.1-8b`, and a 3B-class model, and plot accuracy vs model size per prompt. The hypothesis is that prompt_a_verbose's explicit preconditions become load-bearing below a certain capability threshold — the point where the model stops inferring constraints from the schema and starts relying on the system prompt to tell it what not to do. That threshold is the actionable finding: it tells you whether you need verbose prompts in production and at what model tier the cheaper terse prompt becomes unsafe.

**A/B variable chosen for signal, not for safety.** The verbosity axis was chosen because it is the only free variable remaining after ruling out correctness-required instructions. With a real week I would design the prompt variants first and the case set second, so the cases are adversarial specifically against the dimension under test — rather than inheriting a correctness-focused case set and then finding the only safe variable is word count.

## Reproducing

```bash
export GROQ_API_KEY=your_key_here   # https://console.groq.com — free, no credit card

make run          # full eval (Phase 1: A/B + Phase 2: fault injection)
make agent        # interactive REPL
make eval-fail    # global fault injection — all three tools fail simultaneously
```

Requires Python ≥ 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
make install      # uv sync
```

Results are written to `eval_results.json` and merged on each run — individual cases can be re-run without touching the rest:

```bash
# Re-run a single case (e.g. after a 429 crash)
uv run python eval.py --case 5 --prompt prompt_b_terse

# Re-run a full prompt variant only
uv run python eval.py --prompt prompt_b_terse

# Fault injection only (skip Phase 1)
uv run python eval.py --fault-only
```

Groq free tier: the harness backs off on 429s if encountered. Switch providers by changing one line in `llm/__init__.py`.

## File Map

```
agent.py          — tool-agnostic agent loop
eval.py           — adversarial evaluation harness (20 cases, A/B, fault injection)
                    supports --case / --prompt / --fault-only for partial runs
tools.py          — tool implementations (manage_tasks, convert_units, get_weather)
fault.py          — wrap_tools() fault injection — test infra only, no prod knowledge
db.py             — SQLite schema, TaskStatus enum, connection helpers
hooks.py          — Hook middleware (LoggingHook, TimingHook)
prompts.py        — three system prompts for multi-prompt comparison
cases.py          — 20 eval cases + dynamic FAULT_CASES derivation
scoring.py        — pure scoring functions (no I/O)
llm/
  base_provider.py   — abstract LLMProvider interface
  groq_provider.py   — Groq implementation with retry + 400 handling (active)
  nvidia_provider.py — NVIDIA NIM implementation
  gemini_provider.py — Gemini implementation
  __init__.py        — provider factory (swap active provider here)
docs/
  ANALYSIS.md        — full failure mode documentation (11 entries, historical + current)
```
# AgentAdversarialEval
