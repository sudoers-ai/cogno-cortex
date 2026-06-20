"""``SkillBus`` — provider-based skill dispatch.

The bus maps a skill name → its execution provider. ``LocalProvider`` runs an
in-process ``BaseTool`` (the only provider cortex ships); the ``SkillProvider``
Protocol is the seam a host plugs shell/http/remote providers into (those carry
subprocess/network + security decisions that are host concerns).

Ported from the parent ``cogno.skills.bus`` — the os/JSONL debug logging is dropped
in favour of the house-rule structured logger (lazy ``key=value``, no handlers).
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Protocol, runtime_checkable

from cogno_cortex.base import ToolContext
from cogno_cortex.types import SkillManifest, SkillResult

logger = logging.getLogger(__name__)


@runtime_checkable
class SkillProvider(Protocol):
    """Execution backend for a class of skills."""

    def supports(self, manifest: SkillManifest) -> bool:
        """Return True if this provider can execute the given manifest."""
        ...

    async def invoke(
        self, manifest: SkillManifest, context: ToolContext,
        tool_args: Optional[dict[str, Any]] = None,
    ) -> SkillResult:
        """Execute the skill and return a :class:`SkillResult`."""
        ...


class LocalProvider:
    """Runs skills that carry a ``tool_class`` (a ``BaseTool`` subclass), in-process."""

    def supports(self, manifest: SkillManifest) -> bool:
        return manifest.tool_class is not None

    async def invoke(
        self, manifest: SkillManifest, context: ToolContext,
        tool_args: Optional[dict[str, Any]] = None,
    ) -> SkillResult:
        if manifest.tool_class is None:
            raise RuntimeError(f"manifest '{manifest.name}' has no tool_class")
        tool = manifest.tool_class(**(tool_args or {}))
        return await tool.run(context)


class SkillNotFoundError(KeyError):
    """Raised by the bus when a skill name has no registered manifest."""


class SkillBus:
    """Dispatches skill invocations to the first registered provider that supports them."""

    def __init__(self) -> None:
        self.providers: list[SkillProvider] = []
        self._manifests: dict[str, SkillManifest] = {}

    def register_provider(self, provider: SkillProvider) -> None:
        self.providers.append(provider)

    def register_manifest(self, manifest: SkillManifest) -> None:
        self._manifests[manifest.name] = manifest

    def get_manifest(self, skill_name: str) -> Optional[SkillManifest]:
        return self._manifests.get(skill_name)

    async def invoke(
        self, skill_name: str, context: ToolContext,
        tool_args: Optional[dict[str, Any]] = None,
    ) -> SkillResult:
        """Execute a skill by name.

        Raises:
            SkillNotFoundError: the name has no registered manifest.
            RuntimeError:       no provider supports the manifest.
        """
        manifest = self._manifests.get(skill_name)
        if manifest is None:
            raise SkillNotFoundError(skill_name)
        for provider in self.providers:
            if provider.supports(manifest):
                result = await provider.invoke(manifest, context, tool_args)
                result.skill_name = skill_name  # dispatched name wins over a generic tool name
                logger.debug("event=skill_invoked name=%s provider=%s status=%s",
                             skill_name, manifest.provider_type, result.status)
                return result
        raise RuntimeError(f"no provider supports skill '{skill_name}'")
