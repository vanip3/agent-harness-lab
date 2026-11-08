# agent-harness-lab: harness engineering with AI security

An AI agent harness built by hand in plain Python, then attacked, evaluated and governed. It covers the layer around a language model: what the model is told, what it's allowed to do, and how you prove the controls actually work.

**The model proposes, the harness decides.** The model only ever *asks* for a tool; plain Python decides whether it runs. Every security rule lives in code, not in the prompt.

> Learning project. Local model, fake data, one user. Not production software: see [Limitations](#limitations).

---

## What it does

A sales assistant for a fictional company, DemoCo Analytics. It runs on a local model (`qwen2.5:7b` through Ollama) and has seven tools: look up a customer, read files from a sandbox folder, check revenue, a safe calculator, load a skill, get the time, and **send a proposal to a customer**: the one action with a real-world effect.

Every tool call passes through a pipeline before it runs:

1. **Unknown tool?** Is it a real tool?
2. **Permission:** may this user's role use it? (The role comes from the application, never from the model.)
3. **Arguments:** required, no extras, text only, length-limited.
4. **Approval:** a person says yes before anything is sent to a customer.

Then each tool has its own check: `read_file` refuses any path outside its sandbox, the calculator parses arithmetic without `eval()`, SQL is always parameterised. Every step is recorded to a trace log.

## What I found

### 1. A planted document can hijack the agent

I planted an instruction in a meeting-notes file, pointing at a fake confidential file outside the sandbox (`info.txt`, with a canary string). With the sandbox switched off for the demo, **the attack worked on the 7th attempt**: it needed a neutral file name (the model refused a file called `secrets.txt`, then read the same content as `info.txt`) and a question inviting it to follow references.

### 2. Controls in code stopped every attack that fooled the model in testing

16 eval cases, each run 3 times with the guardrails off and 3 times on (96 runs, scored from the trace, not just the answer):

| | Guardrails off | Guardrails on |
|---|---|---|
| Runs passed | 38 / 48 | 45 / 48 |
| Model **tried** to read the confidential file | 4 of 9 | 4 of 9 |
| Model **reached** it | 4 | **0** |
| Permission and approval cases | 21 / 21 | 21 / 21 |

The model was fooled just as often in both modes. What changed was the path check in `read_file`, which refuses the request whatever the model believes. The other guardrail, marking tool output as untrusted data, made **no measurable difference** to how often the model was fooled. And the model **never warned the user** about a planted instruction (0 of 12 manual runs, 0 of 6 eval runs).

Cases: `evals/cases.json`. Raw results: `evals/results/`.

### 3. Controls are tested without the model

46 automated tests (`pytest`, a few seconds, no model needed) force each attack directly: 7 path-escape attempts, calculator code injection, SQL injection, smuggled arguments, a forbidden role, a rejected approval, a runaway model. Breaking the path check on purpose makes 8 of them fail, which shows the tests can catch a broken control.

## Governance

I also assessed the agent the way a bank's risk team would:

- **A risk register of ten risks**, each rated twice with a likelihood × impact matrix: **inherent** (evidence from the guardrails-off runs) and **residual** (evidence from the guardrails-on runs and tests), with controls by type (preventive, detective, corrective), a response and owners. Two risks remain above appetite: prompt injection, and the agent having more access than the user should.
- **A check against the OWASP Top 10 for LLM Applications (2025)**, which found three gaps (supply chain, system prompt leakage, misinformation) and one risk OWASP doesn't cover: duplicate actions on retry.

## Run it

Windows, PowerShell, Python 3.12, [Ollama](https://ollama.com) installed.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
ollama pull qwen2.5:7b
```

```powershell
# Ask the agent something (role: sales, engineering or finance)
python -m harness.loop "What is Acme Retail's monthly spend?" --role sales

# A proposal: you'll be asked to approve it
python -m harness.loop "Send Acme Retail a proposal to upgrade to DemoCo Sync at 10% off" --role sales

# The tests (no model needed)
python -m pytest tests -v

# One eval case, or the full eval (about 40 minutes)
python -m evals.run_evals --only approval-rejected
python -m evals.run_evals --mode both --repeats 3

# Show the last run's trace
python -m harness.trace
```

**Web UI (optional):** a chat with a role dropdown, a live Activity panel showing every decision (tool ran, blocked and why, approval, injection warning, canary alarm), Approve/Reject buttons for proposals, and a demo switch that turns the guardrails off for one run only.

```powershell
pip install -r requirements-ui.txt
python -m ui.app          # then open http://127.0.0.1:7860
```

Gradio is kept in a separate requirements file because it adds about 40 packages; the agent itself needs two.

**See it in action:** [docs/DEMO.md](docs/DEMO.md) walks through six recorded scenarios with screenshots: a normal question, forbidden data, a rejected and an approved proposal, and the injection attack with the guardrails on and off.

`--unguarded` switches off the sandbox and the untrusted-output markers **for the injection demo only**. It's off by default, prints a warning, and is recorded in the trace.

## Layout

| Folder | What's there |
|---|---|
| `harness/` | The loop, the system prompt, permissions, the middleware pipeline, guardrails, tracing |
| `tools/` | The seven tools and the fake company database |
| `sandbox/`, `skills/` | The only files `read_file` can reach; the skills the agent can load |
| `evals/` | Eval cases, the runner and saved results |
| `tests/` | The automated control tests |
| `ui/` | The optional web UI |


## Limitations

- **Small evidence base:** 16 cases, 3 runs per mode, one small local model. Differences of a few runs are signals, not findings.
- **No real login:** the role is typed in with `--role`. A deployment must take it from sign-in.
- **Not an isolated sandbox:** the sandbox is a path check in one tool, not a separate environment.
- **No monitoring or incident process:** alerts are written to a log nobody watches, and nothing can recall a sent proposal.
- **Tests run by hand:** nothing runs them automatically on every change yet.
- **Some eval checks are rough proxies:** "did the agent warn the user" is a keyword check.
- **The trace log stores everything the agent read**, including the fake secret in the injection demo.

Before any deployment it would need real sign-in, an isolated environment, monitoring, an incident process and tests that run on every change.

## Data

Everything is fake. DemoCo Analytics, its customers and its revenue are made up. `info.txt` is a deliberately fake "confidential" file with a canary string, used to detect leaks in the injection demo.

## How it was built

Built step by step as a learning project. Planning and designing it was the exciting part: the controls, the attack and how to evaluate them. It was then developed with AI assistance (Claude Code).

## Next

- Persistence: save and resume a run, so an approval can wait for hours (Step 10), then durable workflows with Temporal, where retries must not send a proposal twice.
- A small web UI that shows the approval step and the trace live.
- Red-team tooling (garak, PyRIT) for a larger attack set.
- Run the tests automatically on every change.
