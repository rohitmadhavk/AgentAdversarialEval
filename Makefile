.PHONY: run eval agent install

# Primary target — required by assignment spec.
# Uses Groq LPU (openai/gpt-oss-120b) for sub-second per-call latency.
# Token cost per call on 8b-instant is ~5-6x lower than 70b-versatile,
# keeping the full 40-call run well within Groq's 100k TPD free quota.
run:
	GROQ_API_KEY=$$GROQ_API_KEY uv run python eval.py

# Alias
eval: run

# Interactive agent REPL — also Groq for speed.
agent:
	GROQ_API_KEY=$$GROQ_API_KEY uv run python agent.py

install:
	uv sync