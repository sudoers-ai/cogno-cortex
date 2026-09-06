"""``CortexDispatcher`` — the bridge from skills to cogno-anima's tool contract.

This is the keystone: it implements cogno-anima's ``ToolDispatcher`` (and
``ToolPolicyDispatcher``), so the EGO / cogno-soma see skills as ordinary tools and
never know what a "skill" is. ``tools_schema()`` renders the selected manifests as
OpenAI tool defs; ``execute()`` runs the skill via the bus and maps ``SkillResult``
→ ``ToolResult``; the policy methods read the manifest's ``mutating`` / ``destructive``
flags so the EGO's read-only mask and confirmation gate work for skills too.

The host ranks skills first (``SkillRegistry.rank`` against the NER tags) and passes
the chosen ``names`` — or omits them to expose all registered skills. A skill is
NOT a tool: it is a richer thing (manifest + provider + impl) that *resolves to* one
tool here. The ``ToolDispatcher`` contract is the unifier; merge cortex with an MCP
or native dispatcher via ``cogno_anima.tools.CompositeDispatcher``.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from cogno_anima.types import ToolResult

from cogno_cortex.base import ToolContext
from cogno_cortex.bus import LocalProvider, SkillBus, SkillNotFoundError, SkillProvider
from cogno_cortex.loader import register_all
from cogno_cortex.registry import SkillRegistry
from cogno_cortex.types import SkillManifest


class CortexDispatcher:
    """A cogno-anima ``ToolDispatcher`` (+ ``ToolPolicyDispatcher``) backed by skills."""

    def __init__(
        self,
        registry: SkillRegistry,
        bus: SkillBus,
        *,
        names: Optional[Sequence[str]] = None,
        backend: Any = None,
        metadata: Optional[dict] = None,
        trace_id: str = "",
    ) -> None:
        """
        Args:
            registry:  source of manifests (for schemas + policy flags).
            bus:       executes the skills (must have a provider + the manifests registered).
            names:     the skill names to expose this turn (e.g. ``registry.rank(tags)``);
                       ``None`` → expose every registered skill.
            backend:   the ``LLMBackend`` injected into each skill's ``ToolContext``.
            metadata:  extra context handed to every skill (domains, user query, ...).
            trace_id:  correlation id stamped on the ``ToolContext``.
        """
        self._registry = registry
        self._bus = bus
        self._names = list(names) if names is not None else registry.skill_names()
        self._backend = backend
        self._metadata = metadata or {}
        self._trace_id = trace_id

    def _manifest(self, name: str):
        return self._registry.get(name)

    def tools_schema(self) -> list[dict]:
        schemas = []
        for name in self._names:
            m = self._manifest(name)
            if m is not None:
                schemas.append(m.to_tool_schema())
        return schemas

    async def execute(self, name: str, arguments: dict) -> ToolResult:
        context = ToolContext(backend=self._backend, trace_id=self._trace_id,
                              metadata=dict(self._metadata))
        try:
            result = await self._bus.invoke(name, context, tool_args=arguments)
        except SkillNotFoundError:
            # hallucinated / unknown tool name → recoverable, EGO self-corrects
            return ToolResult(output="", ok=False, error=f"unknown tool: {name}")
        manifest = self._manifest(name)
        mutating = bool(manifest.mutating) if manifest else False
        # Pure transport: the skill's promise travels, this layer decides nothing about it.
        asks = bool(result.needs_confirmation)
        if result.ok:
            return ToolResult(output=str(result.payload), ok=True, side_effect=mutating,
                              needs_confirmation=asks)
        # A FAILED call reports no side effect. ``mutating`` is a property of the TOOL, read
        # from the manifest per NAME before anything ran, so copying it here would say "this
        # booking wrote something" about a booking the skill rejected. Nothing is lost: the
        # per-name question still has an answer (``is_mutating``); what stops is the RESULT
        # claiming it. A skill that wrote and only then failed is not representable either way
        # — the old ``True`` did not mean that, it meant "this tool is the kind that writes".
        return ToolResult(output="", ok=False, error=str(result.payload), side_effect=False,
                          needs_confirmation=asks)

    # ── ToolPolicyDispatcher ──────────────────────────────────────────────
    def is_mutating(self, name: str) -> bool:
        m = self._manifest(name)
        return bool(m.mutating) if m else True  # unknown → conservative (masked read-only)

    def requires_confirmation(self, name: str) -> bool:
        m = self._manifest(name)
        return bool(m.destructive) if m else False


def build_dispatcher(
    manifests: Sequence[SkillManifest],
    *,
    names: Optional[Sequence[str]] = None,
    backend: Any = None,
    metadata: Optional[dict] = None,
    trace_id: str = "",
    providers: Optional[Sequence[SkillProvider]] = None,
) -> CortexDispatcher:
    """Manifests in, a ready :class:`CortexDispatcher` out — the four lines everybody writes.

    A registry (for ranking + policy flags) and a bus (for execution) are not two decisions:
    every skill a caller registers has to reach BOTH, and ``register_all`` exists because
    registering in one and forgetting the other is a skill that ranks and cannot run, or runs
    and never gets offered. Assembling them is therefore not a place where callers differ —
    it is the same four statements in this library's README, in its example, in three of its
    unit tests and in an integration test, and once more in the host that drove this helper
    out, whose fourteen call sites all funnel through that single copy. A shape repeated that
    often with no variation belongs to the library, not to each caller.

    ``providers`` defaults to a single :class:`~cogno_cortex.bus.LocalProvider` (in-process
    ``tool_class`` execution), which is what a skill authored as a ``BaseTool`` needs. It is a
    parameter rather than a hardcoded choice because the bus takes several: a caller adding a
    remote provider would otherwise have to abandon this helper and hand-roll the assembly
    again, which is the fork this function exists to prevent.

    The remaining arguments are :class:`CortexDispatcher`'s own and mean exactly what they
    mean there — ``names`` limits what is exposed this turn (``None`` → every registered
    skill), ``backend`` is the ``LLMBackend`` each skill's ``ToolContext`` receives,
    ``metadata`` is the extra context handed to every skill, ``trace_id`` the correlation id.

    Nothing here is a policy: it composes what the caller passed and returns the bare
    dispatcher. A caller that gates writes, filters by tenant, or wraps the result in
    anything wraps THIS — the assembly is mechanical, and what may be executed is not.
    """
    registry = SkillRegistry()
    bus = SkillBus()
    for provider in (providers if providers is not None else [LocalProvider()]):
        bus.register_provider(provider)
    register_all(list(manifests), registry, bus)
    return CortexDispatcher(registry, bus, names=names, backend=backend,
                            metadata=metadata, trace_id=trace_id)
