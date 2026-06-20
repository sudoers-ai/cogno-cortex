"""Shared test doubles: a sample MathTool skill + a fake LLM backend."""

import pytest

from cogno_cortex import BaseTool, SkillManifest, SkillResult, ToolContext


class MathTool(BaseTool):
    """A trivial in-process skill: basic arithmetic (no LLM)."""

    a: float
    op: str
    b: float

    @property
    def name(self) -> str:
        return "math"

    @property
    def description(self) -> str:
        return "Basic arithmetic over two numbers."

    async def run(self, context: ToolContext) -> SkillResult:
        ops = {"+": self.a + self.b, "-": self.a - self.b,
               "*": self.a * self.b, "/": (self.a / self.b if self.b else None)}
        val = ops.get(self.op)
        if val is None:
            return SkillResult(skill_name=self.name, payload="invalid op or divide-by-zero",
                               status="error")
        return SkillResult(skill_name=self.name, payload=val, evidence=[f"{self.a}{self.op}{self.b}"])


MATH_MANIFEST = SkillManifest(
    name="math",
    description="Basic arithmetic over two numbers.",
    tags=["math", "calculation"],
    parameters={
        "type": "object",
        "properties": {
            "a": {"type": "number"}, "op": {"type": "string"}, "b": {"type": "number"}},
        "required": ["a", "op", "b"],
    },
    tool_class=MathTool,
)


class FakeBackend:
    """An LLMBackend stub for BasePromptTool tests."""

    model = "fake"

    async def generate(self, system, prompt):
        return f"echo:{prompt}", 5, 3


@pytest.fixture
def math_tool_cls():
    return MathTool


@pytest.fixture
def math_manifest():
    return MATH_MANIFEST


@pytest.fixture
def fake_backend():
    return FakeBackend()
