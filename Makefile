.PHONY: run eval eval-fail eval-multi-turn agent install

# Primary target — required by assignment spec.
# Uses Groq LPU (openai/gpt-oss-120b) for sub-second per-call latency.
# Token cost per call on 8b-instant is ~5-6x lower than 70b-versatile,
# keeping the full 40-call run well within Groq's 100k TPD free quota.
run:
	GROQ_API_KEY=$$GROQ_API_KEY uv run python eval.py

# Alias
eval: run

# Global fault injection: all three tools fail simultaneously.
eval-fail:
	FORCE_FAIL=manage_tasks,convert_units,get_weather GROQ_API_KEY=$$GROQ_API_KEY uv run python eval.py

# Multi-turn only: tests the stateful tool across conversation turns.
eval-multi-turn:
	GROQ_API_KEY=$$GROQ_API_KEY uv run python eval.py --multi-turn-only

# Interactive agent REPL — also Groq for speed.
agent:
	GROQ_API_KEY=$$GROQ_API_KEY uv run python agent.py

install:
	uv sync