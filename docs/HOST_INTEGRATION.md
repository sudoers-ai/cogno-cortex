# Host integration — cogno-cortex

cortex turns **skills** (in-process `BaseTool` + manifest) into a **tool dispatcher**
the EGO can use. This guide maps the seams.

## 1. The pieces

| Piece | Role |
|---|---|
| `BaseTool` / `BasePromptTool` | author a skill; its Pydantic fields are the tool args. |
| `SkillManifest` | declarative metadata: tags, parameters schema, `mutating`/`destructive`, instructions. |
| `SkillRegistry` | holds manifests; `rank(tags)` orders them by NER-tag overlap. |
| `SkillBus` + `SkillProvider` | executes a skill via a provider; `LocalProvider` runs in-process. |
| `discover` / `register_all` | load skills from disk (`SKILL.md` + a `BaseTool`). |
| `CortexDispatcher` | **the bridge**: implements cogno-anima's `ToolDispatcher` (+ policy). |

## 2. Per-turn flow

```python
# once, at startup:
registry, bus = SkillRegistry(), SkillBus()
bus.register_provider(LocalProvider())
register_all(discover(skills_dir), registry, bus)

# per turn, after NER:
tags = ctx.intent.domains + ctx.intent.mandatory_tags
chosen = registry.rank(tags, max_results=5)          # narrow to the relevant skills
dispatcher = CortexDispatcher(
    registry, bus,
    names=chosen,                # omit → expose all registered skills
    backend=llm_backend,         # injected into each skill's ToolContext
    metadata={"domain": tags},   # any context the skill should see
)
await pipe.run_turn(ctx, cfg, dispatcher=dispatcher)   # cogno-soma
```

Build the dispatcher per turn (cheap) so `names`/`metadata` reflect the current turn.

## 3. Skill → tool mapping (what the EGO sees)

- `tools_schema()` = the chosen manifests as OpenAI tool defs (a manifest with no
  `parameters` falls back to a `{query: string}` schema).
- `execute(name, args)`: runs the skill via the bus; `SkillResult.ok` →
  `ToolResult(ok=True, output=str(payload), side_effect=manifest.mutating)`; a skill
  returning `status="error"` → recoverable `ToolResult(ok=False)`; an unknown name →
  recoverable `ToolResult(ok=False, error="unknown tool: …")` so the EGO self-corrects.
- a skill that **raises** propagates (a bug/infra fault is not silently swallowed).
- policy: `is_mutating` / `requires_confirmation` read the manifest flags, so the
  EGO read-only mask and confirmation gate apply to skills (an unknown name is
  treated conservatively: assumed mutating, no confirmation).

## 4. Custom providers (shell / http / remote)

cortex ships only `LocalProvider`. Plug others via the `SkillProvider` Protocol —
they carry subprocess/network + security decisions that are host concerns:

```python
class HttpProvider:
    def supports(self, manifest): return manifest.provider_type == "http"
    async def invoke(self, manifest, context, tool_args=None) -> SkillResult: ...

bus.register_provider(HttpProvider())   # checked in registration order, first match wins
```

## 5. Composing with MCP / native tools

A persona's `allowed_modules` may mix sources. Each is a `ToolDispatcher`; merge:

```python
from cogno_anima.tools import CompositeDispatcher
dispatcher = CompositeDispatcher([cortex_dispatcher, mcp_dispatcher, native_dispatcher])
```

## 6. Feedback + metering

`SkillRegistry.apply_feedback(name, "good"|"bad"|"dangerous")` nudges a skill's
`performance_rating` (a ranking tie-breaker). `SkillResult.usage` carries token
counts for LLM-driven skills — feed them to `cogno-meter`; cortex does not meter or
price (manifest `pricing_model`/`unit_cost` are metadata only).

## 7. What stays yours

Concrete skills (the product), shell/http/remote providers, persona selection
(`cogno-persona`), RBAC, metering, MCP transport. cortex is the framework; you bring
the skills and the policy.
