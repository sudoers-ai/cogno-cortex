# cogno-cortex

**The in-process skills framework for the Cogno stack.**

A *skill* is a richer thing than a tool: a `BaseTool` implementation **+** a
`SkillManifest` (tags, policy flags, instructions) for discovery and ranking.
cortex is the layer that authors, discovers, ranks and executes skills — and then
**bridges them to a plain tool** via `CortexDispatcher`, so the EGO / `cogno-soma`
see ordinary tools and never know what a "skill" is.

cortex ships the **framework, not the skills** (like `cogno-persona` ships the
store, not the personas). It is infra-agnostic: in-process execution only; shell /
http / remote providers are a host seam.

```
SKILL.md + BaseTool ─▶ SkillRegistry.rank(NER tags) ─▶ CortexDispatcher
                                                              │ (implements
                                                              ▼  cogno-anima's
                                              soma.run_turn(dispatcher=…) → EGO
                                                                 ToolDispatcher)
```

## Install

```bash
pip install cogno-cortex      # pulls cogno-anima + cogno-synapse + pydantic
```

> The sibling cogno libs are not on PyPI yet — install them from git first
> (`cogno-homeo`, `cogno-synapse`, `cogno-anima`); see `.github/workflows/ci.yml`.

## Author a skill

```python
from cogno_cortex import BaseTool, SkillResult, ToolContext

class MathTool(BaseTool):
    a: float
    op: str          # the Pydantic fields ARE the tool arguments
    b: float

    @property
    def name(self): return "math"
    @property
    def description(self): return "Basic arithmetic."

    async def run(self, ctx: ToolContext) -> SkillResult:
        val = {"+": self.a + self.b, "*": self.a * self.b}[self.op]
        return SkillResult(skill_name=self.name, payload=val)
```

Pair it with a `SKILL.md` (frontmatter: `name`, `description`, `tags`, `priority`,
`mutating`, `destructive` + operational instructions in the body) in a directory,
and `discover()` loads it.

## Wire it to the EGO

```python
from cogno_cortex import (SkillRegistry, SkillBus, LocalProvider,
                          CortexDispatcher, discover, register_all)

registry, bus = SkillRegistry(), SkillBus()
bus.register_provider(LocalProvider())
register_all(discover("./skills"), registry, bus)

chosen = registry.rank(ctx.intent.domains + ctx.intent.mandatory_tags)   # NER-driven
dispatcher = CortexDispatcher(registry, bus, names=chosen, backend=llm_backend)

# hand it straight to cogno-soma:
await pipe.run_turn(ctx, cfg, dispatcher=dispatcher)
```

`CortexDispatcher` implements cogno-anima's `ToolDispatcher` **and**
`ToolPolicyDispatcher`: `tools_schema()` renders the chosen manifests; `execute()`
runs the skill and maps `SkillResult → ToolResult`; `is_mutating` / `requires_confirmation`
read the manifest flags so the EGO's read-only mask + confirmation gate work for
skills too.

## Skills + MCP + native tools together

A persona may draw tools from several sources at once. Each source is a
`ToolDispatcher`; merge them with `cogno_anima.tools.CompositeDispatcher`:

```python
from cogno_anima.tools import CompositeDispatcher
dispatcher = CompositeDispatcher([cortex_dispatcher, mcp_dispatcher, native_dispatcher])
```

The `ToolDispatcher` contract is the unifier — skill / MCP / native are just
sources behind it. The persona declares modules **by name**; the host resolves each
to a source and composes.

## What stays at the host

The concrete skills (shell/web/browser/...), shell/http/remote **providers**
(subprocess/network + security), persona selection, metering (`cogno-meter`), RBAC.
cortex is the framework; the host plugs providers via the `SkillProvider` Protocol.

## The Cogno ecosystem

`cogno-cortex` is one organ of **[Cogno](https://github.com/sudoers-ai)** — a family of
small, composable, Apache-2.0 libraries that together form a complete
conversational-agent platform. Each library owns a single concern and stays
infra-agnostic; a **host** assembles them into a running agent:

![The Cogno ecosystem](docs/assets/cogno-ecosystem.svg)

The open-source libraries are the organs; the **host is the body** that joins
them. Our reference host — `cogno-host`, with its `cogno-ui` dashboard — is the
private product layer, but it holds no special powers: everything it does rides
on the public seams documented in each library's `docs/HOST_INTEGRATION.md`, so
you can assemble a body of your own.

## Development

```bash
pip install -e ".[dev]"
pytest tests/unit -q            # fast, no network
pytest tests/integration -q     # real EGO over Ollama, auto-skips if absent
ruff check cogno_cortex tests && mypy cogno_cortex
python examples/host_min.py     # offline demo: discover → rank → bridge → execute
```

Apache-2.0.
