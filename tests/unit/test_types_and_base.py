"""SkillManifest / SkillResult contracts + BaseTool / BasePromptTool."""


from cogno_cortex import BasePromptTool, BaseTool, SkillManifest, SkillResult, ToolContext


def test_to_tool_schema_with_parameters(math_manifest):
    schema = math_manifest.to_tool_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "math"
    assert schema["function"]["parameters"]["required"] == ["a", "op", "b"]


def test_to_tool_schema_default_query_when_no_params():
    m = SkillManifest(name="search", description="web search")
    params = m.to_tool_schema()["function"]["parameters"]
    assert params["properties"]["query"]["type"] == "string"
    assert params["required"] == ["query"]


def test_skill_result_ok():
    assert SkillResult(skill_name="x", payload=1).ok is True
    assert SkillResult(skill_name="x", payload="boom", status="error").ok is False


def test_manifest_policy_flags_default_safe():
    m = SkillManifest(name="x")
    assert m.mutating is False and m.destructive is False


async def test_base_tool_runs(math_tool_cls):
    tool = math_tool_cls(a=2, op="*", b=3)
    res = await tool.run(ToolContext())
    assert res.payload == 6 and res.ok


def test_base_tool_args_schema(math_tool_cls):
    props = math_tool_cls.args_schema()["properties"]
    assert {"a", "op", "b"} <= set(props)


async def test_base_prompt_tool(fake_backend):
    class Summ(BasePromptTool):
        text: str

        @property
        def name(self):
            return "summarize"

        @property
        def description(self):
            return "Summarize text."

        @property
        def prompt_template(self):
            return "Summarize: {text}"

    res = await Summ(text="hello").run(ToolContext(backend=fake_backend))
    assert res.payload == "echo:Summarize: hello"
    assert res.usage == {"tokens_in": 5, "tokens_out": 3}


# ── the description a model reads has exactly one home ────────────────────────────────
#
# ``BaseTool.description`` was an ``@abstractmethod`` until 2026-08-24, which forced every
# skill author to write a SECOND description that nothing consumes: ``to_tool_schema`` renders
# the MANIFEST's. Measured on the reference host, 10 of 12 skills had drifted — silently,
# because it is the only inert duplicate (``name`` and ``parameters`` are duplicated the same
# way and never drifted: a wrong name does not dispatch, a wrong parameter fails the call).
# One was found the expensive way: a description promising a date form the parser lacked,
# failing 50-86% of its calls, "fixed" by editing only the property — which changed nothing
# the model ever saw.

def test_a_skill_need_not_write_a_second_description():
    """The property is optional now. A tool that declares none still builds and still runs.

    Mutation: restore ``@abstractmethod`` and this fails at instantiation."""

    class Bare(BaseTool):
        q: str = ""

        @property
        def name(self) -> str:
            return "bare"

        async def run(self, context: ToolContext) -> SkillResult:
            return SkillResult(skill_name=self.name, payload="ok")

    assert Bare().description == ""
    assert SkillManifest(name="bare", description="what the model reads",
                         tool_class=Bare).to_tool_schema()["function"]["description"] == (
        "what the model reads")


def test_the_schema_the_model_receives_comes_from_the_MANIFEST():
    """Not from the property — the whole point. When the two disagree the manifest wins, so a
    host maintaining both is maintaining one string nobody reads."""

    class Divergent(BaseTool):
        q: str = ""

        @property
        def name(self) -> str:
            return "divergent"

        @property
        def description(self) -> str:
            return "WHAT THE PROPERTY SAYS"

        async def run(self, context: ToolContext) -> SkillResult:
            return SkillResult(skill_name=self.name, payload="ok")

    published = SkillManifest(name="divergent", description="WHAT THE MANIFEST SAYS",
                              tool_class=Divergent).to_tool_schema()["function"]["description"]
    assert published == "WHAT THE MANIFEST SAYS"
    assert Divergent().description not in published
