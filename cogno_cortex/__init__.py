"""cogno-cortex — the in-process skills framework for the Cogno stack.

Skills are authored as ``BaseTool`` subclasses + ``SkillManifest`` metadata,
ranked against NER tags by ``SkillRegistry``, executed by ``SkillBus`` (via a
``SkillProvider`` — ``LocalProvider`` ships), and discovered from disk by the
loader. ``CortexDispatcher`` bridges them to cogno-anima's ``ToolDispatcher`` so the
EGO / cogno-soma see skills as ordinary tools — merge with MCP/native sources via
``cogno_anima.tools.CompositeDispatcher``.
"""

from cogno_cortex.base import BasePromptTool, BaseTool, ToolContext
from cogno_cortex.bus import (
    LocalProvider,
    SkillBus,
    SkillNotFoundError,
    SkillProvider,
)
from cogno_cortex.dispatcher import CortexDispatcher
from cogno_cortex.loader import (
    discover,
    load_skill_dir,
    parse_frontmatter,
    register_all,
)
from cogno_cortex.registry import SkillRegistry
from cogno_cortex.types import SkillManifest, SkillResult

__all__ = [
    "BaseTool",
    "BasePromptTool",
    "ToolContext",
    "SkillManifest",
    "SkillResult",
    "SkillRegistry",
    "SkillBus",
    "SkillProvider",
    "LocalProvider",
    "SkillNotFoundError",
    "CortexDispatcher",
    "discover",
    "load_skill_dir",
    "register_all",
    "parse_frontmatter",
]

__version__ = "0.1.0"
