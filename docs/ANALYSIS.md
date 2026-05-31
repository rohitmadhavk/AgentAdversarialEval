# Failure Mode Analysis

Full documentation of every failure observed across all provider/model combinations during eval development. Entries marked **[Historical]** occurred on earlier models/providers and are not reproduced on the current setup (`openai/gpt-oss-120b` on Groq). Entries marked **[Current]** were observed in the final run. The provider abstraction (`llm/base_provider.py`, one-line swap in `llm/__init__.py`) is what made iterating across four provider/model combinations tractable — each switch required zero harness changes. The final run covers three system prompts (`prompt_a_verbose`, `prompt_b_terse`, `prompt_c_positive`) across all 20 cases.

---

## 1. Malformed Function-Call Generation — `tool_use_failed` (HTTP 400) [Historical]

*Observed on: Groq `llama-3.3-70b-versatile`. Not reproduced on `openai/gpt-oss-120b`.*

**What happened:** Cases 7 ("What is 15% of 340?" — since replaced) and 11 ("Should I bring a jacket to Berlin tomorrow?") crashed with:

```
Error code: 400 — tool_use_failed
failed_generation: '<function=calculate{"expression": "340 * 0.15"}</function>'
```

The model emitted syntactically malformed function-call markup — the JSON object was appended directly to the function name without the expected separator. The Groq API caught this and rejected the generation.

**Root cause:** `llama-3.3-70b-versatile` has a phrasing-sensitive failure in its function-calling fine-tune. Percentage expressions and conditional weather questions appear to be edge cases where the tokenisation or generation template diverges. This is reproducible.

**Fix:** `GroqProvider.complete()` now catches `BadRequestError`. When `tool_use_failed` is detected it returns `LLMResponse(text=None, tool_calls=[], stop_reason="end_turn")` — the agent produces a text fallback rather than crashing, and the eval harness records a clean failure rather than a crash.

**Note on tool replacement:** The original `calculate` tool (arithmetic via `eval()`) was replaced with `convert_units` (pure lookup-table unit conversion). Beyond the security concern — stripping `__builtins__` does not fully sandbox `eval()` — the replacement produces a more interesting disambiguation surface: `convert_units` vs `get_weather` requires the agent to reason about whether the numeric value is *already known* vs *needs to be fetched*. This is a harder and more realistic decision than arithmetic vs weather.

---

## 2. Daily Token Quota Exhaustion [Historical]

*Observed on: Groq `llama-3.3-70b-versatile` free tier (100k TPD). `openai/gpt-oss-120b` completed two full runs with no 429s.*

**What happened:** After ~22 API calls (prompt_a's 20 cases + a couple of extras), the Groq free-tier daily token quota (100 k TPD) was exhausted. Every subsequent call failed with HTTP 429 `type=tokens`. This wiped out all 20 cases of `prompt_b_terse`.

**This is not a code bug.** The eval harness correctly catches these as crashes and records them in `eval_results.json`. The Groq SDK retries per-minute rate limits (429 `type=requests`) automatically; daily-quota 429s are surfaced immediately since no amount of waiting within the same run resolves them.

**Resolution:** Switched to NVIDIA NIM free tier (40 RPM, 1000 RPD). Added per-case filtering: `uv run eval.py --case 5 --prompt prompt_b_terse` re-runs a single case and merges the result back into `eval_results.json` without touching the rest. This is the same checkpoint/resume pattern used in production eval pipelines — the free-tier constraint made it necessary to build it properly rather than leaving it as a future item.

---

## 3. DB Autoincrement Bleed [Fixed — affected all providers]

*A harness bug, not model-specific. Fixed before the final run.*

**What happened:** `reset_db()` deleted all task rows but did not reset the SQLite autoincrement counter. Tasks created by `prompt_a_verbose` (IDs 1–3) caused `prompt_b_terse` tasks to start at ID 4. Case 4 of `prompt_b` ("Delete the first task") generated a delete call targeting `task_id=2`, which no longer existed — the model correctly picked the tool but the operation silently no-oped.

**Fix:** `reset_db()` now also executes `DELETE FROM sqlite_sequence WHERE name='tasks'` so IDs restart from 1 for every prompt run.

---

## 4. Weather Tool SSL Failure [Historical]

*Observed with Open-Meteo in this environment. Resolved by switching to NWS API (`api.weather.gov`). Current results show zero weather tool errors.*

**What happened (earlier runs):** Open-Meteo calls failed with SSL certificate errors. Tool selection was scored as a pass (correct intent) while recording `tool_errors: [true]` — this cleanly separated tool selection accuracy from tool reliability, which is the right design.

**Resolution:** Switched from Open-Meteo to the NWS API (`api.weather.gov`) via `httpx`. The NWS API uses standard CA certificates. Cities were updated to US-only to match NWS coverage. Current results show zero tool errors on weather cases.

---

## 5. Cross-Provider Behavioural Differences [Historical — documents the multi-provider journey]

*The current active model is `openai/gpt-oss-120b` on Groq. The differences below were observed when running the same 20 cases across Groq (`llama-3.3-70b-versatile`), Gemini (`gemini-flash-lite`), and NVIDIA NIM (`llama-3.3-70b-instruct`). They are recorded here because they shaped the harness design and the provider abstraction, not because they affect the final results.*

Running the same 20 cases across three providers with the same schemas revealed two concrete differences:

**Case 4 ("Delete the first task") — confirmation loop on Gemini.** On Gemini, the model entered a verification loop: list → delete → list again → delete again → list again, hitting `MAX_ROUNDS=5` and returning `(no response)`. On NVIDIA NIM, it listed once, deleted, and responded cleanly. Same prompt, same schema, different looping behaviour — the model's instruction-following fine-tune determines whether it over-verifies stateful operations.

**`tool_use_failed` (HTTP 400) — Groq-specific.** Cases 7 and 11 crashed with malformed function-call markup on Groq (`llama-3.3-70b-versatile`) but ran cleanly on NVIDIA NIM (`llama-3.3-70b-instruct`). The same model family, different serving infrastructure and possibly a different fine-tune revision. The `BadRequestError` handler in `GroqProvider` was necessary on Groq; `NvidiaProvider` has the same handler but it never fired.

---

## 6. Prompt Authority vs. Agent Behaviour Under Fault [Historical — resolved in current prompt design]

*Observed on an earlier `prompt_b_terse` design. Not reproduced in the current run.*

**What happened:** An earlier version of `prompt_b_terse` had no explicit fault-reporting instruction. Under fault injection, the model retried each failing tool 4× before giving up. `prompt_a_verbose` had *"If a tool returns an error, explain it plainly. Do not retry unless asked."* and never exhibited this behaviour.

**Why it happened:** Both prompts receive a structured `{"error": "..."}` payload as the tool result — not a raised exception. The model treats this as a result and re-evaluates. Without an explicit no-retry rule, the model infers retry is the correct response. With the rule, it reports the error and stops.

**Resolution:** The current `prompt_b_terse` includes *"if a tool errors, report it plainly"* in its rules. Both prompts now call each failing tool exactly once and return a clean error message. See also Failure Mode 9.

---

## 7. Optional-Field Sentinel Bug — `"omit"` Injected as Integer [Historical]

*Observed on: Groq `llama-3.3-70b-versatile`. `openai/gpt-oss-120b` does not emit `"omit"` sentinels. The `_rescue_type_coercion()` fix remains in the codebase as a defensive measure.*

**What happened:** Case 02 (`prompt_b_terse`) failed with:

```
Error code: 400 — tool_use_failed
failed_generation: '<function=manage_tasks>{"action": "list", "task_id": "omit", "title": "omit"}</function>'
```

The model filled optional integer fields with the string `"omit"` as a placeholder. Groq validates schema types server-side and rejected the call because `task_id` is declared `"type": "integer"` but received a string.

**Root cause:** A model generation habit, not a prompt failure. The model receives the full JSON schema including `"required": ["action"]` which makes `task_id` and `title` optional. Despite this, `llama-3.3-70b-versatile` occasionally fills every field using `"omit"` as an explicit "not applicable" signal. This is independent of prompt wording.

**Fix:** `_rescue_type_coercion()` was extended to handle non-numeric sentinels: if `int(v)` raises `ValueError`, the key is dropped entirely rather than propagating the exception. The result is a valid `{"action": "list"}` call with no spurious fields.

**Why this is worth fixing rather than accepting as a scored failure:** The model correctly identified the tool and action. The `"omit"` sentinels are an artefact of the generation template, not a reasoning error. Dropping them produces exactly what a correct generation would have produced.

---

## 8. Happy-Path Cases 1–4 Are a Stateful Sequence, Not Independent [Design decision — all providers]

**What this means:** Cases 1–4 run in order — add → list → complete → delete — on the same database state. Case 3 ("Mark task number 1 as complete") can only succeed if Case 1 already ran; Case 4 ("Delete the first task") assumes the row exists. This is a **stateful sequence**, not 10 independent tool-selection tests.

**Why we document rather than redesign:** Making each case self-contained would require embedding setup steps into the prompt ("You have a task called X with ID 1 — now complete it"), which changes what the LLM is reasoning over and produces a different eval signal. The current design intentionally tests the agent's ability to handle a realistic CRUD sequence. What it does *not* test is recovery from mid-sequence failures (e.g., what happens if Case 2 fails and Case 3 assumes the list is populated). That is the multi-turn evaluation called out in the README.

---

## 9. Parametric Memory Answering After Tool Failure [Historical — resolved in current prompt design]

*Observed on an earlier `prompt_b_terse` design. Not reproduced in the current run.*

**What happened:** In an earlier `prompt_b_terse` design (no explicit fault-reporting instruction), fault injection Case 5 (`convert_units`, injected to always fail) caused the agent to retry the failing tool 4 times. After exhausting retries, it returned `"100 km is about 62.14 miles."` — the correct answer — with no mention of a failure. The tool never succeeded; the model recalled the answer from training data.

**Why this is dangerous:** This passes scoring (correct tool selected, error recorded, non-empty response) and produces a correct answer in this instance. But the model cannot distinguish *"I have this stored in my weights"* from *"I should produce a plausible-sounding answer"* — both feel equally confident. On a `get_weather` case where the answer is not in training data, the same pattern produces a confident hallucination after tool failure.

**Resolution:** The current `prompt_b_terse` includes *"if a tool errors, report it plainly"* in its rules. Both prompts now report errors cleanly on the first failure with no retries. In the current run, prompt_b Case 5 returns `"The conversion tool returned an error: [injected] convert_units tool failed."` — correct behaviour. See also Failure Mode 6.

---

## 10. Fault Error Masquerading as OOS Abstention — prompt_c_positive [Current]

*Observed on: `openai/gpt-oss-120b`, prompt_c_positive, fault injection Case 08 (`get_weather`).*

**What happened:** Under fault injection, `get_weather` was replaced with a stub that raises `RuntimeError("[injected] get_weather tool failed")`. prompt_c_positive called the tool, received the error, and returned:

```
"I can't help with that."
```

This is identical to the response for a correct OOS abstention (e.g. Case 20, Cairo). prompt_a_verbose and prompt_b_terse both returned explicit error messages:

```
prompt_a: "The weather lookup failed — unable to provide current conditions for New York."
prompt_b: "The weather tool returned an error: [injected] get_weather tool failed."
```

**Why the harness passes it:** The spec's graceful-degradation criteria are: (1) correct tool selected, (2) error recorded, (3) agent survived with a non-empty response. All three are satisfied. The harness correctly measures the spec requirement.

**Why it matters in production:** The user receives a response that is indistinguishable from "this request is out of scope." They do not know whether the service is unavailable, whether the tool is broken, or whether they asked the wrong question. In a production system this causes silent data gaps — users stop asking rather than retrying or escalating. prompt_a's explicit fault-reporting instruction prevents this.

**Root cause (corrected):** prompt_c *does* include an explicit fault-reporting instruction — *"If a tool returns an error, report it plainly and stop. Do not retry."* — equivalent in intent to prompt_a's version. The model received the instruction and ignored it. The mechanism: prompt_c's affirmative scope framing (`"Use this for ANY question whose answer requires current weather data"`) appears to prime the model to treat the `{"error": "..."}` tool response as evidence that the request is out of scope, routing to the OOS refusal path rather than the fault-reporting path. The RULES instruction is present in context but overridden by the TOOLS section's framing-driven inference: *"the tool said it can't help → this must not be a question the tool answers → I can't help with that."* This is a more dangerous finding than a missing instruction: affirmative scope language can silently suppress an explicitly stated rule, and the presence of the rule provides no guarantee it will fire under fault conditions.

**Why this drove the ship recommendation to prompt_a:** Between prompt_a and prompt_c (the only two prompts that pass all 20 cases), prompt_a explicitly handles the two scenarios where silent failure is most dangerous: multi-step stateful operations (Case 4) and tool error transparency (fault injection Case 08). prompt_c passes the benchmark on both but fails in production on both.

**Scorer blind spot:** The current harness cannot distinguish `"I can't help with that"` (correct OOS) from `"I can't help with that"` (swallowed tool error). Fixing this requires LLM-as-judge scoring: a single API call per fault case asking *"did the agent correctly explain why it couldn't fulfil this request?"* This is the highest-priority improvement to the eval harness.

---

## 11. Lifestyle Framing Masks Weather Intent — Case 11 [Historical — resolved by dataset correction]

*Originally observed on `openai/gpt-oss-120b`, all runs, both prompt variants. Also observed on all other providers tested. Resolved by correcting the case wording.*

**What happened:** The original Case 11 wording was *"Should I bring a jacket to Miami tomorrow?"* Both prompts returned a refusal on every run. Neither called `get_weather`.

**Root cause — two-layer problem:**

*Layer 1 — dataset design error.* `get_weather` returns current conditions only. A question about *tomorrow* cannot be answered by the tool; refusing was technically the correct behaviour. The case was labelled `expected_tool = get_weather` but the tool cannot satisfy the request. This was a bad case, not a bad prompt.

*Layer 2 — genuine model failure on the lifestyle framing.* Even corrected to *"today"*, the failure mode exists: the model pattern-matches "bring a jacket" as a request for personal lifestyle advice rather than a weather lookup. Intent classification fails before tool selection. The OOS refusal fires on what the model believes is an advice-seeking request.

**Resolution:** Case 11 was corrected to *"Should I bring a jacket to my meeting in Miami today?"*. All three prompts pass the corrected case. The dataset error was the actual blocker.

**Why prompt fixes don't resolve the lifestyle-framing failure independently:** A chain-of-thought instruction was tested against the original wording — *"Before making any decision, state in one sentence what the user actually needs"*. It did not resolve it. The model verbalised *"the user wants to know if they should bring a jacket"*, inheriting the lifestyle framing. The CoT step executes but the misclassification occurs inside it. On the corrected *"today"* wording, the temporal anchor makes the weather-factual intent unambiguous, so the prompt fix is unnecessary — the model classifies correctly without it.

**Why this matters beyond the score:** The surface behaviour of the original failure was indistinguishable from a correct OOS refusal. The current harness cannot tell the difference between *"correctly identified as out-of-scope"* and *"misclassified as out-of-scope"*. An LLM-as-judge scorer asking *"did the agent understand the user's intent?"* would catch this class of failure; substring abstention matching cannot.
