"""
Integration: a cortex skill executed end-to-end through the real EGO + Ollama.

Wires a math skill into a registry/bus, exposes it via CortexDispatcher, and lets
the real EGO (text-fallback path over mistral) pick + call it. Proves the bridge:
skill → CortexDispatcher → EGO tool call → SkillResult → ToolResult. Auto-skipped
without Ollama. temperature=0.0 for determinism.
"""

import httpx
import pytest

from cogno_synapse import OllamaBackend
from cogno_anima.stages.ego import EgoStage
from cogno_anima.types import (
    IntentResult,
    NoumenoResult,
    PipelineContext,
    StageMetrics,
)

from cogno_cortex import (
    CortexDispatcher,
    LocalProvider,
    SkillBus,
    SkillRegistry,
)
from tests.conftest import MATH_MANIFEST

MODEL = "mistral:latest"


async def is_ollama_available() -> bool:
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            return (await client.get("http://localhost:11434/")).status_code == 200
    except Exception:
        return False


SYSTEM = (
    "You are an assistant's execution engine. For ANY arithmetic you MUST call the "
    "math tool — never compute it yourself. When done, reply with the result.")


def _m(stage):
    return StageMetrics(stage=stage, elapsed_ms=1.0, tokens_in=1, tokens_out=1, model="test")


def _ctx(task: str) -> PipelineContext:
    noumeno = NoumenoResult(
        original=task, rewritten=task, context_turn="", language="en",
        canonical_language="en", drift_score=0.0, drift_tag="PASS_THROUGH",
        changed=False, confidence=1.0, change_subject=False, subject_similarity=1.0,
        context_used=False, preserved_terms=[], rewrite_warnings=[], metrics=_m("noumeno"))
    intent = IntentResult(
        intent_class="ACTION_REQUEST", sentiment="NEUTRAL", confidence=1.0,
        temporal_class="TIMELESS", triad_signal="EGO", goal=task, domains=["MATH"],
        metrics=_m("ner"))
    return PipelineContext(user_input=task, noumeno=noumeno, intent=intent)


@pytest.mark.asyncio
async def test_ego_executes_cortex_skill():
    if not await is_ollama_available():
        pytest.skip("Local Ollama server (http://localhost:11434) is not running.")
    backend = OllamaBackend(model=MODEL, temperature=0.0)

    reg, bus = SkillRegistry(), SkillBus()
    bus.register_provider(LocalProvider())
    reg.register(MATH_MANIFEST)
    bus.register_manifest(MATH_MANIFEST)

    # the host would rank by NER tags; here MATH is the only candidate
    disp = CortexDispatcher(reg, bus, names=reg.rank(["MATH"]), backend=backend)
    assert [s["function"]["name"] for s in disp.tools_schema()] == ["math"]

    ctx = await EgoStage().process(
        _ctx("What is 12 multiplied by 8?"), backend, disp, system_prompt=SYSTEM)
    res = ctx.ego_result

    assert res is not None
    executed = [t.tool for t in res.tools_executed]
    assert "math" in executed, f"expected math, got {executed}; draft={res.draft!r}"
