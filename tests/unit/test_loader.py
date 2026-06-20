"""Loader: frontmatter parsing + on-disk skill discovery + register_all."""

from pathlib import Path

import pytest

from cogno_cortex import (
    LocalProvider,
    SkillBus,
    SkillRegistry,
    discover,
    load_skill_dir,
    parse_frontmatter,
    register_all,
)

_SKILL_PY = '''
from cogno_cortex import BaseTool, SkillResult, ToolContext


class GreetTool(BaseTool):
    who: str = "world"

    @property
    def name(self) -> str:
        return "greet"

    @property
    def description(self) -> str:
        return "Greet someone."

    async def run(self, context: ToolContext) -> SkillResult:
        return SkillResult(skill_name=self.name, payload=f"hello {self.who}")
'''

_SKILL_MD = """---
name: greet
description: Greet someone by name.
tags:
  - social
  - greeting
priority: 7
mutating: true
---
Use this skill to greet the user. Always be warm.
"""


@pytest.fixture
def skill_root(tmp_path: Path) -> Path:
    d = tmp_path / "greet"
    d.mkdir()
    (d / "SKILL.md").write_text(_SKILL_MD, encoding="utf-8")
    (d / "greet_tool.py").write_text(_SKILL_PY, encoding="utf-8")
    return tmp_path


def test_parse_frontmatter_keys_and_list():
    meta, body = parse_frontmatter(_SKILL_MD)
    assert meta["name"] == "greet"
    assert meta["tags"] == ["social", "greeting"]
    assert meta["priority"] == "7"
    assert body.startswith("Use this skill")


def test_parse_frontmatter_no_frontmatter():
    meta, body = parse_frontmatter("just text")
    assert meta == {} and body == "just text"


def test_load_skill_dir(skill_root):
    man = load_skill_dir(skill_root / "greet")
    assert man is not None
    assert man.name == "greet"
    assert man.tags == ["social", "greeting"]
    assert man.priority == 7
    assert man.mutating is True
    assert man.tool_class is not None
    assert man.skill_instructions.startswith("Use this skill")


def test_load_skill_dir_without_skill_md(tmp_path):
    (tmp_path / "empty").mkdir()
    assert load_skill_dir(tmp_path / "empty") is None


def test_discover_and_register(skill_root):
    manifests = discover(skill_root)
    assert [m.name for m in manifests] == ["greet"]

    reg, bus = SkillRegistry(), SkillBus()
    bus.register_provider(LocalProvider())
    register_all(manifests, reg, bus)
    assert reg.get("greet") is not None
    assert bus.get_manifest("greet") is not None


def test_discover_missing_root(tmp_path):
    assert discover(tmp_path / "nope") == []


def test_broken_skill_file_is_skipped(tmp_path):
    """A .py that fails to import is logged + skipped; manifest has no tool_class."""
    d = tmp_path / "broken"
    d.mkdir()
    (d / "SKILL.md").write_text("---\nname: broken\n---\nbody", encoding="utf-8")
    (d / "bad.py").write_text("import does_not_exist_xyz\n", encoding="utf-8")
    man = load_skill_dir(d)
    assert man is not None and man.name == "broken"
    assert man.tool_class is None


def test_skill_dir_without_tool_py(tmp_path):
    d = tmp_path / "docs_only"
    d.mkdir()
    (d / "SKILL.md").write_text("---\nname: docs_only\ntags: a, b\n---\nx", encoding="utf-8")
    man = load_skill_dir(d)
    assert man.tool_class is None
    assert man.tags == ["a", "b"]      # comma-separated inline tags


async def test_discovered_skill_executes(skill_root):
    man = load_skill_dir(skill_root / "greet")
    from cogno_cortex import ToolContext
    tool = man.tool_class(who="Ana")
    res = await tool.run(ToolContext())
    assert res.payload == "hello Ana"
