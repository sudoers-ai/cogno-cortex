"""SkillBus + LocalProvider + SkillProvider protocol."""

import pytest

from cogno_cortex import (
    LocalProvider,
    SkillBus,
    SkillManifest,
    SkillNotFoundError,
    SkillProvider,
    ToolContext,
)


def _bus(*manifests, provider=None):
    bus = SkillBus()
    bus.register_provider(provider or LocalProvider())
    for m in manifests:
        bus.register_manifest(m)
    return bus


def test_local_provider_supports(math_manifest):
    assert LocalProvider().supports(math_manifest) is True
    assert LocalProvider().supports(SkillManifest(name="x")) is False  # no tool_class


async def test_bus_invokes_local(math_manifest):
    bus = _bus(math_manifest)
    res = await bus.invoke("math", ToolContext(), tool_args={"a": 4, "op": "+", "b": 1})
    assert res.payload == 5
    assert res.skill_name == "math"


async def test_bus_unknown_skill_raises(math_manifest):
    with pytest.raises(SkillNotFoundError):
        await _bus(math_manifest).invoke("ghost", ToolContext())


async def test_bus_no_provider_raises():
    bus = SkillBus()  # no provider registered
    bus.register_manifest(SkillManifest(name="x", tool_class=object))
    with pytest.raises(RuntimeError, match="no provider"):
        await bus.invoke("x", ToolContext())


async def test_bus_overrides_skill_name():
    """A generic tool_class name is overridden by the dispatched skill name."""
    from cogno_cortex import BaseTool, SkillResult

    class Generic(BaseTool):
        @property
        def name(self):
            return "generic"

        @property
        def description(self):
            return "g"

        async def run(self, context):
            return SkillResult(skill_name="generic", payload="ok")

    bus = _bus(SkillManifest(name="specific", tool_class=Generic))
    res = await bus.invoke("specific", ToolContext())
    assert res.skill_name == "specific"


async def test_local_provider_invoke_without_tool_class_raises():
    with pytest.raises(RuntimeError, match="no tool_class"):
        await LocalProvider().invoke(SkillManifest(name="x"), ToolContext())


def test_custom_provider_satisfies_protocol():
    class HttpProvider:
        def supports(self, manifest):
            return manifest.provider_type == "http"

        async def invoke(self, manifest, context, tool_args=None):
            ...

    assert isinstance(HttpProvider(), SkillProvider)
