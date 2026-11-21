# Modelpin on SRE Copilot

This is a fork of [neeltom92/sre-copilot](https://github.com/neeltom92/sre-copilot) (MIT, see `LICENSE`), made to
measure one real app's switch off a retiring model. It isn't the original project and isn't endorsed by its author.

SRE Copilot's default model, `claude_model` in `config.py`, is `claude-sonnet-4-5-20250929`. Anthropic retires that
model on 30 Nov 2026 and names `claude-sonnet-5-5` as its replacement. This fork adds, and changes nothing else:

- `scenarios/`: 8 conversations, each one of the app's own rules (ask for the environment before an APM query,
  confirm before acknowledging or resolving an incident, use the sidebar's cluster and namespace, and so on). Each
  sends the app's own `SYSTEM_PROMPT` (from `agent.py`) and its 15 tools (from `tools/langchain_tools.py`), as the
  app sends them; `scripts/modelpin_scenarios.py` writes them. The tool results are fixed, made-up examples.
- `modelpin.yaml` and `model.txt`: [Modelpin](https://pypi.org/project/modelpin/) settings, and the model id alone.
- `.modelpin/baseline-claude-sonnet-4-5-20250929.json`: 10 runs of each scenario on the current model, recorded
  before the retirement.
- `.github/workflows/modelpin.yml`: on a pull request that changes `model.txt`, Modelpin replays each scenario 5 times
  on the new model and compares the tool calls and refusals with the recorded runs.

What this doesn't measure: changes in meaning (no grader model is set), what the app says when it calls no tool, the
app's own `temperature=0` (Modelpin's runs use its defaults on both models), and anything the made-up tool results
don't exercise.
