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
from cogno_cortex.bus import SkillBus, SkillNotFoundError
from cogno_cortex.registry import SkillRegistry


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
        side_effect = bool(manifest.mutating) if manifest else False
        if result.ok:
            return ToolResult(output=str(result.payload), ok=True, side_effect=side_effect)
        return ToolResult(output="", ok=False, error=str(result.payload), side_effect=side_effect)

    # ── ToolPolicyDispatcher ──────────────────────────────────────────────
    def is_mutating(self, name: str) -> bool:
        m = self._manifest(name)
        return bool(m.mutating) if m else True  # unknown → conservative (masked read-only)

    def requires_confirmation(self, name: str) -> bool:
        m = self._manifest(name)
        return bool(m.destructive) if m else False
