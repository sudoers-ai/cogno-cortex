"""A reference skill: basic arithmetic. Discovered via the sibling SKILL.md."""

from cogno_cortex import BaseTool, SkillResult, ToolContext


class MathTool(BaseTool):
    a: float
    op: str   # one of + - * /
    b: float

    @property
    def name(self) -> str:
        return "math"

    @property
    def description(self) -> str:
        return "Basic arithmetic over two numbers."

    async def run(self, context: ToolContext) -> SkillResult:
        ops = {"+": self.a + self.b, "-": self.a - self.b, "*": self.a * self.b,
               "/": (self.a / self.b if self.b else None)}
        val = ops.get(self.op)
        if val is None:
            return SkillResult(skill_name=self.name, payload="invalid op or divide-by-zero",
                               status="error")
        return SkillResult(skill_name=self.name, payload=val, evidence=[f"{self.a}{self.op}{self.b}"])
