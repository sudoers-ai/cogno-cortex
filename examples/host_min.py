"""Minimal, **offline** host wiring for cogno-cortex.

Runs with no network: discovers the reference skill from ``examples/skills/``,
ranks it against NER-style tags, bridges it to cogno-anima via CortexDispatcher,
and executes it — the same dispatcher you would hand to ``cogno-soma``'s EGO.

    python examples/host_min.py
"""

import asyncio
from pathlib import Path

from cogno_cortex import (
    CortexDispatcher,
    LocalProvider,
    SkillBus,
    SkillRegistry,
    discover,
    register_all,
)

SKILLS_DIR = Path(__file__).resolve().parent / "skills"


async def main():
    # 1. discover skills from disk (SKILL.md + a BaseTool) and register them
    registry, bus = SkillRegistry(), SkillBus()
    bus.register_provider(LocalProvider())
    manifests = discover(SKILLS_DIR)
    register_all(manifests, registry, bus)
    print("discovered:", registry.skill_names())

    # 2. rank against the turn's NER tags (the host pulls these from ctx.intent)
    chosen = registry.rank(["NER.MATH", "calculation"])
    print("ranked for tags [MATH]:", chosen)

    # 3. bridge the chosen skills to cogno-anima's ToolDispatcher
    dispatcher = CortexDispatcher(registry, bus, names=chosen)
    print("tools the EGO sees:", [s["function"]["name"] for s in dispatcher.tools_schema()])
    print("is_mutating(math):", dispatcher.is_mutating("math"))

    # 4. the EGO would call this; here we invoke it directly (math needs no LLM)
    result = await dispatcher.execute("math", {"a": 12, "op": "*", "b": 8})
    print("execute math(12 * 8) ->", result.output, "| ok:", result.ok)

    # 5. hand `dispatcher` to soma:  await pipe.run_turn(ctx, cfg, dispatcher=dispatcher)
    #    (merge with MCP/native sources via cogno_anima.tools.CompositeDispatcher)


if __name__ == "__main__":
    asyncio.run(main())
