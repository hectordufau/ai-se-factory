# AI Software Engineering Factory

A portfolio-grade, production-style **multi-agent system** that takes a high-level
software requirement and autonomously drives it through the full engineering
lifecycle: product → architecture → implementation → tests → security → review →
release.

Built as evidence for the IgniteTech *Software Engineering Superbuilder (AI-DNA)*
role. Demonstrates: **MCP**, **multi-agent orchestration**, **LLM-in-production**,
and **agentic coding** — with HITL gates, guardrails, and an eval harness.

## Stack
- Python 3.11+
- LLM: OpenCode Zen gateway (`opencode/big-pickle`) — OpenAI-compatible
- Custom orchestration core (no black-box framework)
- MCP servers (Filesystem, Testing, GitHub, Database, Docs)
- Local / Docker (no real AWS)

## Status
- [x] Phase 0 — scaffold + provider adapter + event bus
- [ ] Phase 1 — orchestration core (DAG, worktree, model router)
- [ ] Phase 2 — specialized agents
- [ ] Phase 3 — MCP servers
- [ ] Phase 4 — guardrails + HITL
- [ ] Phase 5 — eval harness
- [ ] Phase 6 — production hardening

## Quick start (Phase 0)
```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

See `ignitetech-superbuilder/` notes in the Obsidian vault for the full plan.
