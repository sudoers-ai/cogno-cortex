"""Data contracts for the skill framework.

``SkillManifest`` — declarative metadata for registry/ranking + the OpenAI tool
schema the EGO sees. ``SkillResult`` — the structured output a skill returns.

Ported from the parent ``cogno.skills.types`` with the infra-leaning fields
trimmed (XDG paths, sub-doc dirs) and two policy flags added (``mutating`` /
``destructive``) so a :class:`~cogno_cortex.dispatcher.CortexDispatcher` can satisfy
cogno-anima's ``ToolPolicyDispatcher`` and drive the EGO's read-only / confirmation
gates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SkillManifest:
    """Declarative metadata for a registered skill.

    Args:
        name:               Unique skill identifier (e.g. "math", "search").
        description:        One-line capability summary (shown to the model).
        tags:               Discovery tags — matched against NER domains/mandatory_tags.
        parameters:         JSON-Schema for the tool's arguments (OpenAI format). Empty
                            dict → a minimal ``{query: string}`` schema.
        version:            Semver string.
        provider_type:      Execution backend label ("local", "shell", "http", ...).
        priority:           Tie-breaker for equally-scored skills (higher = preferred).
        performance_rating: Adaptive quality score (0..1), nudged by ``apply_feedback``.
        tool_class:         The ``BaseTool`` subclass that implements this skill (for the
                            in-process ``LocalProvider``); ``None`` for provider-only skills.
        skill_instructions: Operational instructions (from SKILL.md) the model may read.
        mutating:           True if the skill writes / causes a side effect (drives the
                            EGO read-only mask).
        destructive:        True if the skill is dangerous and must be confirmed first
                            (drives the EGO confirmation gate).
        pricing_model:      "free" | "per_call" (metadata; metering is cogno-meter's job).
        unit_cost:          Cost per invocation (metadata only).
        timeout_seconds:    Advisory max execution time.
        metadata:           Free-form extra (model name, source dir, etc.).
    """

    name: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    version: str = "0.1.0"
    provider_type: str = "local"
    priority: int = 5
    performance_rating: float = 0.5
    tool_class: Optional[Any] = None
    skill_instructions: str = ""
    mutating: bool = False
    destructive: bool = False
    pricing_model: str = "free"
    unit_cost: float = 0.0
    timeout_seconds: float = 30.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_tool_schema(self) -> dict[str, Any]:
        """Render this manifest as an OpenAI function-calling tool definition.

        With no ``parameters`` declared, falls back to a minimal ``{query: string}``
        schema (the skill reads the raw user query).
        """
        params = self.parameters or {
            "type": "object",
            "properties": {
                "query": {"type": "string",
                          "description": "The user's query or input for this tool"}
            },
            "required": ["query"],
        }
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": params,
            },
        }


@dataclass
class SkillResult:
    """Structured output from a skill execution.

    Args:
        skill_name:    Which skill produced this result.
        payload:       The actual output (text / JSON-serialisable value).
        status:        "success" | "error" | "blocked".
        evidence:      Strings explaining what was done.
        risks:         Risk strings (empty if safe).
        confidence:    0..1 confidence in result quality.
        provider_type: Execution backend used.
        usage:         Token usage if an LLM was involved ({"tokens_in", "tokens_out"}).
        metadata:      Extra context (model name, etc.).
    """

    skill_name: str
    payload: Any
    status: str = "success"
    evidence: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    confidence: float = 1.0
    provider_type: str = "local"
    usage: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "success"
