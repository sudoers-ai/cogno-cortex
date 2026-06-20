"""SkillManifest / SkillResult contracts + BaseTool / BasePromptTool."""


from cogno_cortex import BasePromptTool, SkillManifest, SkillResult, ToolContext


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
