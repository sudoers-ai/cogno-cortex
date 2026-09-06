"""``build_dispatcher``: the assembly, and the two halves it must not let drift apart.

A registry and a bus are not two decisions. Every manifest has to reach BOTH — the registry
so the skill can be ranked and its policy flags read, the bus so it can actually run — and the
failure of registering in only one is silent in opposite directions: a skill that ranks and
cannot run, or one that runs and is never offered. So the tests below assert the two halves
separately rather than trusting one call that happens to work.
"""

from __future__ import annotations

import pytest

from cogno_anima.tools import ToolDispatcher, ToolPolicyDispatcher

from cogno_cortex import (
    CortexDispatcher,
    LocalProvider,
    SkillManifest,
    build_dispatcher,
)


def test_it_returns_a_dispatcher_that_satisfies_both_anima_protocols(math_manifest):
    disp = build_dispatcher([math_manifest])
    assert isinstance(disp, CortexDispatcher)
    assert isinstance(disp, ToolDispatcher)
    assert isinstance(disp, ToolPolicyDispatcher)


def test_every_manifest_reaches_the_REGISTRY(math_manifest):
    """The ranking/schema half: what is not registered is never offered to the model."""
    disp = build_dispatcher([math_manifest, SkillManifest(name="search", description="s")])
    assert {s["function"]["name"] for s in disp.tools_schema()} == {"math", "search"}


@pytest.mark.asyncio
async def test_every_manifest_reaches_the_BUS(math_manifest):
    """The execution half. A manifest in the registry but not the bus renders a perfectly
    good tool schema and then fails at call time — which the schema assertion above cannot
    see, because it never executes anything."""
    disp = build_dispatcher([math_manifest])
    res = await disp.execute("math", {"a": 2, "op": "+", "b": 3})
    assert res.ok is True
    assert "5" in str(res.output)


@pytest.mark.asyncio
async def test_the_local_provider_is_wired_by_default(math_manifest):
    """Without a provider the bus has nothing to execute WITH: the manifests would be
    registered on both halves and the call would still fail. Asserted by executing, since
    that is the only place the provider's absence shows."""
    res = await build_dispatcher([math_manifest]).execute("math", {"a": 1, "op": "*", "b": 4})
    assert res.ok is True


@pytest.mark.asyncio
async def test_a_caller_supplies_its_own_providers(math_manifest):
    """The parameter exists so that adding a provider does not mean abandoning the helper
    and hand-rolling the assembly again — the fork this function exists to prevent."""

    class _Refusing:
        """Supports everything, runs nothing — proves the default was really replaced."""

        def supports(self, manifest) -> bool:
            return True

        async def invoke(self, manifest, arguments, context):
            raise AssertionError("the caller's provider was asked, which is the point")

    disp = build_dispatcher([math_manifest], providers=[_Refusing()])
    with pytest.raises(AssertionError):
        await disp.execute("math", {"a": 1, "op": "+", "b": 1})
    # …and an EMPTY sequence is honoured too, rather than falling back to the default: a
    # caller that passes no provider on purpose gets a bus that executes nothing. The
    # distinction matters — `providers=[]` reaching the default would silently run
    # in-process skills for a caller that deliberately wired none.
    disp = build_dispatcher([math_manifest], providers=[])
    with pytest.raises(RuntimeError):
        await disp.execute("math", {"a": 1, "op": "+", "b": 1})


def test_names_limits_what_is_exposed_without_unregistering_anything(math_manifest):
    both = [math_manifest, SkillManifest(name="search", description="s")]
    disp = build_dispatcher(both, names=["search"])
    assert {s["function"]["name"] for s in disp.tools_schema()} == {"search"}
    # the manifest is still registered — `names` is a per-turn view, not a filter on the
    # registry, which is what makes it safe to rebuild the view every turn.
    assert {s["function"]["name"] for s in build_dispatcher(both).tools_schema()} == {
        "math", "search"}


@pytest.mark.asyncio
async def test_backend_metadata_and_trace_id_reach_the_skill_context(fake_backend):
    """They are ``CortexDispatcher``'s arguments and mean exactly what they mean there — so
    what needs pinning is that the helper FORWARDS them, which a default-only call cannot
    tell apart from a helper that silently drops them."""
    seen: dict = {}

    from cogno_cortex import BaseTool, SkillResult

    class _Spy(BaseTool):
        @property
        def name(self) -> str:
            return "spy"

        @property
        def description(self) -> str:
            return "records its context"

        async def run(self, context) -> SkillResult:
            seen["backend"] = context.backend
            seen["metadata"] = dict(context.metadata or {})
            seen["trace_id"] = context.trace_id
            return SkillResult(skill_name="spy", payload="ok")

    manifest = SkillManifest(name="spy", description="records its context", tool_class=_Spy,
                             parameters={"type": "object", "properties": {}})
    disp = build_dispatcher([manifest], backend=fake_backend,
                            metadata={"tenant_scope": "opaque"}, trace_id="t-42")
    assert (await disp.execute("spy", {})).ok is True
    assert seen["backend"] is fake_backend
    assert seen["metadata"]["tenant_scope"] == "opaque"
    assert seen["trace_id"] == "t-42"


def test_the_policy_flags_survive_the_assembly():
    """``is_mutating`` / ``requires_confirmation`` are read off the manifests through the
    REGISTRY, so a helper that registered only on the bus would answer the EGO's read-only
    mask and confirmation gate with the conservative default for every skill."""
    disp = build_dispatcher([
        SkillManifest(name="read", description="r"),
        SkillManifest(name="write", description="w", mutating=True),
        SkillManifest(name="wipe", description="d", mutating=True, destructive=True),
    ])
    assert disp.is_mutating("read") is False
    assert disp.is_mutating("write") is True
    assert disp.requires_confirmation("write") is False
    assert disp.requires_confirmation("wipe") is True


def test_no_manifests_is_an_empty_dispatcher_not_an_error():
    disp = build_dispatcher([])
    assert disp.tools_schema() == []


def test_it_wraps_nothing_and_decides_nothing(math_manifest):
    """The helper composes what it was given and returns the BARE dispatcher. A caller that
    gates writes or filters by tenant wraps this — pinned because the day the assembly starts
    returning something else, every caller that relied on the type quietly changes shape."""
    assert type(build_dispatcher([math_manifest])) is CortexDispatcher


def test_each_call_builds_an_ISOLATED_registry_and_bus(math_manifest):
    """Two dispatchers from two calls must not see each other's skills: the host builds one
    per turn with that turn's manifests, and shared state would leak one tenant's skill
    catalogue into the next turn's tool list."""
    a = build_dispatcher([math_manifest])
    b = build_dispatcher([SkillManifest(name="search", description="s")])
    assert {s["function"]["name"] for s in a.tools_schema()} == {"math"}
    assert {s["function"]["name"] for s in b.tools_schema()} == {"search"}


def test_the_default_provider_is_the_local_one():
    """Named rather than merely exercised: which provider the default is decides what a
    manifest without a ``tool_class`` does, and the assertion above only proves *some*
    provider ran."""
    disp = build_dispatcher([])
    assert any(isinstance(p, LocalProvider) for p in disp._bus.providers)
