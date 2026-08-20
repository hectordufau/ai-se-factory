"""Validate Level 2 evidence: run the factory against dockerfabricwizard as
repo_root so QA executes the test suite and Security runs static checks, and
the EvalHarness scores real signals (tokens, tests, security findings)."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from factory.agents import build_agents
from factory.agent import AgentContext
from factory.llm import build_client
from factory.model_router import ModelRouter
from factory.mcp_fs import FilesystemMCP
from factory.evals.eval import EvalHarness
from factory.orchestrator import Orchestrator
from factory.task_dag import TaskDag
from factory.cli import build_dag


async def main():
    repo = Path.home() / "workspace" / "dockerfabricwizard"
    fs = FilesystemMCP(repo)
    client = build_client("nous")
    router = ModelRouter()
    agents = build_agents(client, router, mcp_bundle={"filesystem": fs})
    dag = build_dag()
    orch = Orchestrator(dag, agents, repo_root=str(repo))
    result = await orch.run("Improve this Hyperledger Fabric wizard (evidence test)")
    result.metrics["tokens"] = client.total_tokens
    score = EvalHarness().score(result)
    print(EvalHarness().report(score))
    print("\n=== evidence artifacts ===")
    for a in result.artifacts:
        t = a.meta.get("tool")
        if t in ("run_tests", "scan"):
            print(f"  [{a.agent}] {t}: {a.meta}")
    print(f"\n  total tokens: {result.metrics.get('tokens')}")
    print(f"  overall: {score.overall}  success: {result.success}")


if __name__ == "__main__":
    asyncio.run(main())
