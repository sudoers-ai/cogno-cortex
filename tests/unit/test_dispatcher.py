"""CortexDispatcher: the bridge to cogno-anima's ToolDispatcher contract."""


from cogno_anima.tools import ToolDispatcher, ToolPolicyDispatcher

from cogno_cortex import (
    CortexDispatcher,
    LocalProvider,
    SkillBus,
    SkillManifest,
    SkillRegistry,
)


def _wire(*manifests):
    reg, bus = SkillRegistry(), SkillBus()
    bus.register_provider(LocalProvider())
    for m in manifests:
        reg.register(m)
        bus.register_manifest(m)
    return reg, bus


def test_satisfies_anima_protocols(math_manifest):
    reg, bus = _wire(math_manifest)
    disp = CortexDispatcher(reg, bus)
    assert isinstance(disp, ToolDispatcher)
    assert isinstance(disp, ToolPolicyDispatcher)


def test_tools_schema_exposes_all_by_default(math_manifest):
    reg, bus = _wire(math_manifest, SkillManifest(name="search", description="s"))
    names = {s["function"]["name"] for s in CortexDispatcher(reg, bus).tools_schema()}
    assert names == {"math", "search"}


def test_tools_schema_filtered_by_names(math_manifest):
    reg, bus = _wire(math_manifest, SkillManifest(name="search"))
    disp = CortexDispatcher(reg, bus, names=["math"])
    assert [s["function"]["name"] for s in disp.tools_schema()] == ["math"]


def test_names_can_come_from_ranking(math_manifest):
    reg, bus = _wire(math_manifest, SkillManifest(name="search", tags=["web"]))
    disp = CortexDispatcher(reg, bus, names=reg.rank(["math"]))
    assert [s["function"]["name"] for s in disp.tools_schema()] == ["math"]


async def test_execute_success_maps_to_tool_result(math_manifest):
    reg, bus = _wire(math_manifest)
    res = await CortexDispatcher(reg, bus).execute("math", {"a": 6, "op": "/", "b": 2})
    assert res.ok is True
    assert res.output == "3.0"


async def test_execute_error_maps_to_recoverable(math_manifest):
    reg, bus = _wire(math_manifest)
    res = await CortexDispatcher(reg, bus).execute("math", {"a": 1, "op": "/", "b": 0})
    assert res.ok is False
    assert "divide-by-zero" in (res.error or "")


async def test_execute_unknown_is_recoverable(math_manifest):
    reg, bus = _wire(math_manifest)
    res = await CortexDispatcher(reg, bus).execute("ghost", {})
    assert res.ok is False
    assert "unknown tool" in (res.error or "")


async def test_side_effect_reflects_mutating_flag():
    m = SkillManifest(name="write", tool_class=_EchoTool, mutating=True)
    reg, bus = _wire(m)
    res = await CortexDispatcher(reg, bus).execute("write", {})
    assert res.side_effect is True


def test_policy_reads_manifest_flags():
    safe = SkillManifest(name="read")
    danger = SkillManifest(name="drop", mutating=True, destructive=True)
    reg, bus = _wire(safe, danger)
    disp = CortexDispatcher(reg, bus)
    assert disp.is_mutating("read") is False
    assert disp.is_mutating("drop") is True
    assert disp.requires_confirmation("drop") is True
    assert disp.requires_confirmation("read") is False


def test_policy_unknown_is_conservative(math_manifest):
    reg, bus = _wire(math_manifest)
    disp = CortexDispatcher(reg, bus)
    assert disp.is_mutating("ghost") is True          # unknown → masked in read-only
    assert disp.requires_confirmation("ghost") is False


async def test_backend_and_metadata_reach_the_skill():
    seen = {}

    class Spy(_EchoTool):
        async def run(self, context):
            seen["backend"] = context.backend
            seen["meta"] = context.metadata
            return await super().run(context)

    reg, bus = _wire(SkillManifest(name="spy", tool_class=Spy))
    disp = CortexDispatcher(reg, bus, backend="BK", metadata={"domain": "finance"})
    await disp.execute("spy", {})
    assert seen["backend"] == "BK"
    assert seen["meta"] == {"domain": "finance"}


# ── helper skill ──────────────────────────────────────────────────────
from cogno_cortex import BaseTool, SkillResult  # noqa: E402


class _EchoTool(BaseTool):
    @property
    def name(self):
        return "echo"

    @property
    def description(self):
        return "echo"

    async def run(self, context):
        return SkillResult(skill_name=self.name, payload="done")
