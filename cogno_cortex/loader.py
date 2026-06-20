"""``SkillLoader`` — discover on-disk skills (``SKILL.md`` + a ``BaseTool``).

A skill directory contains a ``SKILL.md`` (YAML-ish frontmatter: name/description/
tags/... + operational instructions in the body) and one or more ``.py`` files with
a ``BaseTool`` subclass. ``discover`` scans a root for such directories and returns
``SkillManifest``s (with ``tool_class`` wired to the found ``BaseTool`` and
``skill_instructions`` set to the SKILL.md body). ``register_all`` loads them into a
registry + bus. The XDG/builtins hardcoded paths of the parent are dropped — the
host passes the directories it wants.

Frontmatter parsing mirrors cogno-persona's loader (simple ``key: value`` + ``- list``).
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
import re
from pathlib import Path
from typing import Optional, Type

from cogno_cortex.base import BaseTool
from cogno_cortex.bus import SkillBus
from cogno_cortex.registry import SkillRegistry
from cogno_cortex.types import SkillManifest

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)
_BOOL_TRUE = {"true", "yes", "1"}


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split ``---``-delimited frontmatter from the body. Returns ``(meta, body)``."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    raw, body = m.group(1), m.group(2)
    meta: dict = {}
    key: Optional[str] = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        list_item = re.match(r"\s*-\s+(.*)", line)
        if list_item and key is not None and isinstance(meta.get(key), list):
            meta[key].append(list_item.group(1).strip().strip("'\""))
            continue
        kv = re.match(r"([A-Za-z0-9_]+)\s*:\s*(.*)", line)
        if not kv:
            continue
        key, val = kv.group(1), kv.group(2).strip()
        if val == "":
            meta[key] = []          # a list follows on the next lines
        else:
            meta[key] = val.strip("'\"")
    return meta, body.strip()


def _find_tool_class(skill_dir: Path) -> Optional[Type[BaseTool]]:
    """Import the .py files in ``skill_dir`` and return the first ``BaseTool`` subclass."""
    for py in sorted(skill_dir.glob("*.py")):
        if py.name == "__init__.py":
            continue
        spec = importlib.util.spec_from_file_location(f"_cortex_skill_{py.stem}", py)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001 — a broken skill file must not crash discovery
            logger.warning("event=skill_import_failed file=%s error=%s", py.name, exc)
            continue
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, BaseTool) and obj.__module__ == module.__name__:
                return obj
    return None


def load_skill_dir(skill_dir: Path) -> Optional[SkillManifest]:
    """Build a ``SkillManifest`` from one skill directory (needs a ``SKILL.md``)."""
    md = skill_dir / "SKILL.md"
    if not md.exists():
        return None
    meta, body = parse_frontmatter(md.read_text(encoding="utf-8"))
    name = meta.get("name") or skill_dir.name
    tool_class = _find_tool_class(skill_dir)
    raw_tags = meta.get("tags", [])
    if isinstance(raw_tags, list):
        tags: list[str] = [str(t) for t in raw_tags]
    else:
        tags = [t.strip() for t in str(raw_tags).split(",") if t.strip()]
    return SkillManifest(
        name=name,
        description=meta.get("description", ""),
        tags=tags,
        version=meta.get("version", "0.1.0"),
        provider_type=meta.get("provider", "local"),
        priority=int(meta.get("priority", 5)),
        mutating=str(meta.get("mutating", "false")).lower() in _BOOL_TRUE,
        destructive=str(meta.get("destructive", "false")).lower() in _BOOL_TRUE,
        tool_class=tool_class,
        skill_instructions=body,
        metadata={"source_dir": str(skill_dir)},
    )


def discover(root: Path | str) -> list[SkillManifest]:
    """Discover all skills under ``root`` (each immediate subdir with a ``SKILL.md``)."""
    root = Path(root)
    manifests: list[SkillManifest] = []
    if not root.is_dir():
        return manifests
    for child in sorted(root.iterdir()):
        if child.is_dir():
            man = load_skill_dir(child)
            if man is not None:
                manifests.append(man)
    return manifests


def register_all(
    manifests: list[SkillManifest], registry: SkillRegistry, bus: SkillBus,
) -> None:
    """Register every manifest in both the registry (ranking) and the bus (dispatch)."""
    for man in manifests:
        registry.register(man)
        bus.register_manifest(man)
