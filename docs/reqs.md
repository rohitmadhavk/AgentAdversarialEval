Assignment - Agent, Adversarial Eval

Target: 2 days of focused work. Hard cutoff: 3 days from this email. We read submissions as they arrive. Strong submissions go to interview quickly. Five intern positions.

A heads-up: Claude Code, Cursor, and any AI tooling you like are encouraged - we use them ourselves daily. The catch is this: anyone can one-shot a tutorial-grade version of these in an hour. What we are reading for is the work the LLM cannot do for you - your dataset choice, your experiment design, your honest analysis of where it breaks. Submissions where we can tell the candidate did not actually run the experiments and read the results will be cut quickly.

Build a working agent with three tools and an evaluation harness that punishes the behaviour we care about: choosing the wrong tool, hallucinating when no tool fits, and crashing when a tool fails.

Required:

3 tools, at least one stateful (a tiny SQLite or JSON store you read and write across turns is enough). Tools must be meaningfully different - not three variants of search.
LLM-driven tool selection (no hand-coded routing if-statements).
Graceful degradation: if a tool throws, the agent must keep going, not crash. Build deliberate failures into your eval to verify this.
Evaluation harness with 20 prompts:
10 happy-path prompts, each labelled with the correct tool
5 ambiguous prompts where two tools could plausibly fire - say which you'd prefer and why
5 out-of-scope prompts that no tool can answer - the right behaviour is "I can't help with that," not a hallucinated answer
Report tool-selection accuracy, out-of-scope abstention rate, and end-to-end latency.
Run the eval at least twice with two different system prompts. Show which prompt wins on which dimension. Pick one to ship and justify.
Naming and explaining one observed failure mode is mandatory. "Worked perfectly" is not a valid finding.
Reply to this email with:

A GitHub repo (public, or private with us added) - or a zip
A README (1-3 pages) that walks us through:
Why you picked this assignment
The decisions you made and the alternatives you ruled out
Your headline numbers
One thing you would do differently with another week
A make run command or equivalent so we can reproduce your results on a single machine without exotic setup.
What we are NOT reading for: lines of code shipped, framework brand-recognition, or demo polish. We are reading for whether you understood the problem, made defensible calls, and were honest about where your system breaks.