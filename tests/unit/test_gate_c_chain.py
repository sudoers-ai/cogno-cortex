"""Gate C through the REAL composed chain: skill → bus → dispatcher → EGO.

Gate B (in the EGO) holds a tool by NAME, decided BEFORE anything runs. Gate C is the skill
saying, about THIS call and what it just READ, "I did not commit — ask first". The in-process
route is where that matters most: cortex skills are the ones that read the agenda and the
ledger, which is exactly where "cancelling *this* appointment is two hours away" lives.

Why the chain and not the seam: a field can leave its source and be eaten by a layer in
between, and every layer tested alone still passes. A short-chain test proves the seam exists;
only the real chain proves it CROSSES. So this file asserts the promise where it has to land —
``EgoResult.pending_confirmation`` — and never at the dispatcher.
"""

import json

import pytest

from cogno_anima.stages.ego import EgoStage
from cogno_anima.types import (
    IntentResult, NoumenoResult, PipelineContext, StageMetrics, committed_this_turn,
)

from cogno_cortex import (
    BaseTool, CortexDispatcher, LocalProvider, SkillBus, SkillManifest, SkillRegistry,
    SkillResult,
)

SYS = "You are an executor."


class _CancelTool(BaseTool):
    """A MUTATING skill that reads first and then refuses to commit unasked.

    It is the reason gate C exists: the manifest can say "cancel_appointment mutates", but only
    this code, having read the row, knows the appointment starts in two hours.
    """

    @property
    def name(self):
        return "cancel_appointment"

    @property
    def description(self):
        return "cancel an appointment"

    async def run(self, context):
        if context.metadata.get("user_confirmed"):
            return SkillResult(skill_name=self.name, payload="Cancelled.")
        return SkillResult(
            skill_name=self.name,
            payload="That appointment starts in 2 hours — cancelling now forfeits the slot. "
                    "Confirm and I will cancel it.",
            needs_confirmation=True,
        )


class _Backend:
    """Native-FC double: one tool call, then a closing text."""

    model = "stub-fc"

    def __init__(self):
        self.turns = [
            {"content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {
                "name": "cancel_appointment", "arguments": json.dumps({"id": "a7"})}}]},
            {"content": "Shall I cancel it?"},
        ]

    async def generate(self, system, prompt):
        return "Shall I cancel it?", 1, 1

    async def chat_with_tools(self, messages, tools, tool_choice=None):
        return self.turns.pop(0), 1, 1

    def supports_native_tools(self):
        return True


def _m(stage):
    return StageMetrics(stage=stage, elapsed_ms=0.0, tokens_in=0, tokens_out=0, model="stub")


def _ctx(**meta):
    user = "cancel my appointment"
    ctx = PipelineContext(
        user_input=user,
        noumeno=NoumenoResult(
            original=user, rewritten=user, context_turn="", language="en", drift_score=0.0,
            drift_tag="PASS_THROUGH", changed=False, confidence=0.9, change_subject=False,
            subject_similarity=1.0, context_used=False, preserved_terms=[],
            rewrite_warnings=[], metrics=_m("noumeno")),
        intent=IntentResult(
            intent_class="ACTION_REQUEST", sentiment="NEUTRAL", confidence=0.9,
            temporal_class="PRESENT", triad_signal="EGO", goal="cancel appointment",
            domains=["SCHEDULING"], entities_objects=["appointment"], metrics=_m("ner")),
    )
    ctx.metadata.update(meta)
    return ctx


def _wire(**dispatcher_kwargs):
    manifest = SkillManifest(name="cancel_appointment", tool_class=_CancelTool, mutating=True)
    reg, bus = SkillRegistry(), SkillBus()
    bus.register_provider(LocalProvider())
    reg.register(manifest)
    bus.register_manifest(manifest)
    return CortexDispatcher(reg, bus, **dispatcher_kwargs)


@pytest.mark.asyncio
async def test_a_skill_that_asks_reaches_EgoResult_pending_confirmation():
    """The whole point, asserted at the END of the chain and nowhere earlier."""
    disp = _wire()
    ctx = await EgoStage().process(_ctx(), _Backend(), disp, system_prompt=SYS)

    held = ctx.ego_result.pending_confirmation
    assert held, "the skill asked and the EGO never heard it — the chain does not cross"
    assert [h.tool for h in held] == ["cancel_appointment"]

    # the proposal the contact will see is the SKILL's own text, grounded in what it read
    assert "starts in 2 hours" in held[0].result

    # ...and it is recorded as a non-commit, so nothing downstream can read it as a write
    assert held[0].ok is False and held[0].side_effect is False
    assert committed_this_turn(ctx) is False


@pytest.mark.asyncio
async def test_the_confirmation_travels_back_through_the_skills_OWN_channel():
    """The core never invents an argument name: the answer reaches the skill via the
    ToolContext metadata this lib already owns, and only then does the skill commit."""
    disp = _wire(metadata={"user_confirmed": True})
    ctx = await EgoStage().process(_ctx(), _Backend(), disp, system_prompt=SYS)

    assert ctx.ego_result.pending_confirmation == []
    call = ctx.ego_result.steps[0].tool_calls[0]
    assert call.ok is True and "Cancelled." in call.result
    assert committed_this_turn(ctx) is True, "the confirmed call must count as a write"


@pytest.mark.asyncio
async def test_a_HOST_confirmation_that_never_reached_the_skill_fails_LOUDLY(caplog):
    """The mis-wiring this new route is exposed to, and the reason it is safe anyway.

    The host can confirm through ITS channel (``ego_confirmed``), which the EGO reads. But the
    skill only sees its own ``ToolContext.metadata`` — so if the host wired one and not the
    other, the call is no longer held AND the skill still refuses to commit. Nothing was
    written and there is nobody left to ask.

    ``_refuse_if_still_asking`` turns that into a named failure instead of shipping "done"
    over a turn that wrote nothing. Asserted through the composed chain because the two
    channels belong to different layers and neither one alone can show the collision.
    """
    disp = _wire()                                   # the skill's channel is NOT wired...
    ctx = _ctx(ego_confirmed=True)                   # ...but the host's is
    with caplog.at_level("WARNING", logger="cogno_anima.stages.ego"):
        ctx = await EgoStage().process(ctx, _Backend(), disp, system_prompt=SYS)

    call = ctx.ego_result.steps[0].tool_calls[0]
    assert call.ok is False, "a call that committed nothing must not be recorded as a success"
    assert "CONFIRMED" in (call.error or "") and "Do NOT report this as done" in (call.error or "")
    assert "confirmed_call_still_asks" in caplog.text
    assert committed_this_turn(ctx) is False
