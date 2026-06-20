"""Skill authoring contracts: ``BaseTool`` / ``BasePromptTool`` / ``ToolContext``.

A skill is a ``BaseTool`` subclass: its Pydantic fields ARE the tool's arguments,
and ``run(context)`` executes it, returning a :class:`SkillResult`. ``ToolContext``
carries the injected LLM backend + free-form metadata (the host passes domains,
constraints, the user query, etc.) — note it carries NO pipeline/DB handle: a skill
is infra-agnostic, exactly like the rest of the stack.

Ported from the parent ``cogno.skills.base``; the ``PipelineContext`` coupling of
the parent's ``ToolContext`` is replaced by a plain ``metadata`` dict.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict

from cogno_cortex.types import SkillResult


class ToolContext(BaseModel):
    """Execution context passed to a skill's ``run()``.

    Attributes:
        backend:  an injected ``cogno_synapse.LLMBackend`` (typed ``Any`` to avoid a
                  hard import + circulars); ``None`` for skills that need no LLM.
        trace_id: optional correlation id for observability.
        metadata: extra context from the host (domains, constraints, user query, ...).
    """

    backend: Any = None
    trace_id: str = ""
    metadata: dict[str, Any] = {}
    model_config = ConfigDict(arbitrary_types_allowed=True)


class BaseTool(BaseModel, ABC):
    """Abstract base for all skills. Subclasses declare arguments as Pydantic fields.

    Example::

        class MathTool(BaseTool):
            a: float
            op: str
            b: float

            @property
            def name(self) -> str: return "math"

            @property
            def description(self) -> str: return "Basic arithmetic."

            async def run(self, context: ToolContext) -> SkillResult:
                ...
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique skill name (must match the ``SkillManifest.name``)."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this skill does."""

    @abstractmethod
    async def run(self, context: ToolContext) -> SkillResult:
        """Execute the skill and return a :class:`SkillResult`."""

    @classmethod
    def args_schema(cls) -> dict[str, Any]:
        """JSON-Schema for this skill's arguments (its Pydantic fields)."""
        return cls.model_json_schema()


class BasePromptTool(BaseTool):
    """Convenience base for LLM-driven skills: ``run`` formats a prompt + calls the backend."""

    @property
    @abstractmethod
    def prompt_template(self) -> str:
        """A ``str.format`` template with ``{field_name}`` placeholders."""

    async def run(self, context: ToolContext) -> SkillResult:
        formatted = self.prompt_template.format(**self.model_dump())
        response = await context.backend.generate("You are a specialized tool assistant.", formatted)
        text = response[0] if isinstance(response, tuple) else response
        usage: dict[str, int] = {}
        if isinstance(response, tuple) and len(response) >= 3:
            usage = {"tokens_in": response[1], "tokens_out": response[2]}
        return SkillResult(
            skill_name=self.name, payload=text, status="success",
            evidence=[f"prompt tool '{self.name}' executed"], usage=usage)
