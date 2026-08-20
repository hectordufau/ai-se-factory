"""Drive the AI Factory to improve dockerfabricwizard -> Fabric v2.5 LTS.

Real end-to-end test. Strategy: one focused sub-task per target file, each
with minimal context (only the lines that change), so the small free-tier LLM
follows the <<<FILES>>> output format reliably. Files are written to the
working copy via the scoped FilesystemMCP, then validated with py_compile.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from factory.agents import build_agents
from factory.agent import AgentContext
from factory.llm import build_client
from factory.model_router import ModelRouter
from factory.mcp_fs import FilesystemMCP

REPO = Path.home() / "workspace" / "dockerfabricwizard"

# (target file, minimal context / instruction)
TASKS = [
    (
        "config/versions.py",
        "Create this NEW file (complete content):\n"
        "FABRIC_VERSION = \"2.5.14\"\n"
        "FABRIC_CA_VERSION = \"1.5.15\"\n"
        "FIREFLY_VERSION = \"v1.3.0\"\n",
    ),
    (
        "controllers/build.py",
        "In this file, every Docker image uses ':latest' (e.g. "
        "\"hyperledger/fabric-peer:latest\", \"hyperledger/fabric-orderer:latest\", "
        "\"hyperledger/fabric-ca:latest\", \"hyperledger/fabric-tools:latest\"). "
        "Replace ':latest' with the pinned version constants imported from "
        "config.versions (FABRIC_VERSION / FABRIC_CA_VERSION). Return the COMPLETE "
        "updated file.",
    ),
    (
        "controllers/requirements.py",
        "Two changes, return the COMPLETE updated file:\n"
        "1) The HLF binaries install line:\n"
        "     os.system(\"./install-fabric.sh binary\")\n"
        "   must become:\n"
        "     os.system(\"./install-fabric.sh binary -v 2.5.14\")\n"
        "2) Replace `os.system(\"rm -fR \" + <path>)` calls with "
        "`shutil.rmtree(<path>, ignore_errors=True)` (import shutil already present).\n"
        "3) The FireFly clone branch `v1.2.2` must become the constant "
        "FIREFLY_VERSION (import from config.versions).",
    ),
    (
        "README.md",
        "Add a new '## Versions' section near the top (after the Overview) stating "
        "that Docker Fabric Wizard uses Hyperledger Fabric v2.5 LTS "
        "(FABRIC_VERSION 2.5.14, fabric-ca 1.5.15). Return the COMPLETE updated file.",
    ),
]


def file_context(rel: str) -> str:
    p = REPO / rel
    if not p.exists():
        return f"(file {rel} does not exist yet — create it)\n"
    txt = p.read_text(encoding="utf-8", errors="replace")
    # keep context bounded: full file but truncated if huge
    if len(txt) > 6000:
        txt = txt[:6000] + "\n...[truncated]...\n"
    return f"### CURRENT {rel}:\n{txt}\n"


async def run_task(agents, rel: str, instruction: str) -> tuple[str, bool]:
    backend = agents["backend"]
    requirement = (
        f"TASK: improve '{rel}' for Hyperledger Fabric v2.5 LTS.\n"
        f"{instruction}\n\n"
        "Return ONLY a <<<FILES>>> block with the changed file, format:\n"
        "<<<FILES>>>\nPATH: <repo-relative-path>\n```\n<COMPLETE new file content>\n```\n<<<END>>>\n"
        "Do not add commentary outside the block.\n\n"
        + file_context(rel)
    )
    ctx = AgentContext(requirement=requirement)
    artifacts = await backend.run(ctx)
    written = [a for a in artifacts if a.meta.get("tool") == "filesystem.write" and not a.meta.get("error")]
    ok = len(written) > 0
    return rel, ok


async def main():
    fs = FilesystemMCP(REPO)
    client = build_client("nous")
    router = ModelRouter()
    agents = build_agents(client, router, mcp_bundle={"filesystem": fs})
    results = []
    for rel, instr in TASKS:
        print(f"[factory] task: {rel}")
        rel, ok = await run_task(agents, rel, instr)
        results.append((rel, ok))
        print(f"  -> {'WROTE' if ok else 'NO FILE (model did not emit <<<FILES>>>)'}")
    print("\n=== summary ===")
    for rel, ok in results:
        print(f"  [{'OK' if ok else 'MISS'}] {rel}")
    return all(ok for _, ok in results)


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
