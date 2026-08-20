# AI Software Engineering Factory

A portfolio-grade, **production-style multi-agent system** that takes a software
requirement and autonomously drives it through the full engineering lifecycle:

```
           REQUIREMENT
                │
                ▼
            Planner Agent
                │
                ▼
         Architect Agent  ── HITL GATE (approve design)
        ┌───────┼───────┐
        ▼       ▼       ▼
   Backend  Frontend  Database   (each in its own git worktree)
        └───────┼───────┘
        ┌───────┼───────┐
        ▼       ▼       ▼
      QA      Security   (run tests / scan)
        └───────┼───────┘
                ▼
          Reviewer Agent
                │
                ▼
            Release  ── HITL GATE (approve ship)
                │
                ▼
            Production
```

Built to demonstrate the exact "AI-native engineering" profile the
IgniteTech *Software Engineering Superbuilder* role asks for:
**agents, tools, context, rules, skills, guardrails and evals** — wired as a
real, testable system (not a chatbot).

## What's implemented (6 phases, TDD, 51 tests)

| Layer | Module | Evidence for the role |
|-------|--------|----------------------|
| Provider adapter | `factory/llm.py`, `providers.py` | OpenAI-compatible; **Hermes/Nous `tencent/hy3:free`** + **OpenCode Zen `big-pickle`**; key from local auth files, never hardcoded |
| Model judgment | `factory/model_router.py` | reasoning / coding / fast model classes per task type |
| Orchestration | `factory/orchestrator.py`, `task_dag.py` | topological DAG, parallel waves, per-agent scoped context, HITL gates, circuit breakers |
| Agents | `factory/agents/` | 8 specialized roles with prompts + MCP tool access |
| MCP | `factory/mcp_*` | Filesystem (scoped), Testing (pytest), GitHub (PyGithub), Database (read-only), Docs |
| Guardrails | `factory/guardrails.py` | per-role MCP scope, circuit breaker, gate policy |
| Eval | `factory/evals/eval.py` | scores each run (success, test pass rate, security findings, cost), regression detection, report |
| CLI | `factory/cli.py` | `python -m factory run --requirement "..."` |
| Ops | `Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml` | containerized + CI (pytest on push, smoke on dispatch) |

## Quick start

```bash
cd ~/workspace/ai-se-factory
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

# Unit + integration tests (no network)
pytest -q

# Real LLM end-to-end (calls tencent/hy3:free via Nous, or big-pickle via Zen)
pytest -m smoke

# Drive the factory on a requirement (needs an LLM key in auth files)
python -m factory run --requirement "Build a REST API for a todo app"
```

## How it answers the IgniteTech gaps

- **AI Agents / multi-agent**: 8-agent DAG with parallel execution and
  file-based coordination via the `EventBus` audit trail.
- **MCP (demonstrated application)**: 5 real MCP servers, including a
  GitHub server that opens PRs using your PAT.
- **LLM in production**: the provider adapter is OpenAI-compatible and ships
  with two free providers; the eval harness scores every run.
- **Guardrails / enterprise**: per-role scope, required architectural gate
  before code, circuit breakers, HITL on release.

## Notes

The free LLM tiers are rate-limited: `tencent/hy3:free` (Nous/Hermes) is the
reliable default; `big-pickle` (OpenCode Zen) is available but intermittently
throttled on the free plan. Swap providers with `--provider zen|nous`.
