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

When you are not ranking — you already know which manifests this turn gets — the four
assembly statements are `build_dispatcher`:

```python
from cogno_cortex import build_dispatcher

dispatcher = build_dispatcher(manifests, backend=llm_backend, metadata={"scope": scope})
```

It builds a fresh registry + bus per call, wires a `LocalProvider` (pass `providers=` for
your own), registers every manifest on **both** halves, and returns the bare
`CortexDispatcher`. The two halves are the reason it exists: registering in one and
forgetting the other is silent in opposite directions — a skill that ranks and cannot run,
or one that runs and is never offered. It decides nothing; a caller that gates writes or
filters by tenant wraps the result.

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

## Generic skills (behind extras)

cortex ships the framework and, behind an extra each, the rare skill that is pure MECHANISM —
it knows no tenant, persona, plan or price, and takes everything that decides who may read what
as an injected parameter. Nothing under `cogno_cortex.skills` is imported by `import cogno_cortex`.

| Skill | Extra | What it does |
|---|---|---|
| `consult_documents` | `documents` (pulls `cogno-engram`) | searches a `cogno_engram.DocumentStore`: passages with provenance, or an honest "nothing relevant"; with a budget, reads a document WHOLE (#13) |
| `web_search` | none | searches the public web through a `SearchProvider` the host injects (title, URL, snippet per hit); refuses a query that carries personal data before the provider is called |
| `web_fetch` | `web` (`httpx`, `trafilatura`) | downloads ONE public page and returns its main text, behind SSRF guards (public addresses only, pinned connection, ≤3 redirects, 2 MB, 10 s, HTML/plain text only) and the same personal-data refusal |

```bash
pip install "cogno-cortex[documents]"
```

```python
from cogno_cortex import build_dispatcher
from cogno_cortex.skills.consult_documents import (
    META_DOCUMENTS_ACCESS, DocumentsAccess, offer_consult_documents)

records = []                                   # pre-placed: one ConsultRecord per call
access = DocumentsAccess(store=store, embedder=embedder, embed_model=label,
                         owner_key=owner, profile=reader_profile,
                         hybrid_floor=H, lexical_floor=L,        # required — calibrate them
                         lexical_evidence_floor=E,               # required too; 0 = off
                         user_text=raw_turn, records=records)
manifest = await offer_consult_documents(access)   # None → nothing readable → not offered
if manifest is not None:
    source = build_dispatcher([manifest], metadata={META_DOCUMENTS_ACCESS: access})
```

The full contract — floors, the two fused searches, the record, what the host owns — is in
[`docs/CONSULT_DOCUMENTS.md`](docs/CONSULT_DOCUMENTS.md). Three things a host wires beyond the
snippet above, each OFF until it asks (the wiring is in
[`docs/HOST_INTEGRATION.md`](docs/HOST_INTEGRATION.md) § 7):

- **the whole-document read** (#13): `DocumentsAccess(max_whole_chars=…, whole_doc_chars=…)`
  reads the documents of the shown passages whole, up to a budget, and adds the optional
  `whole`/`document`/`after` arguments to the schema; it needs a store with `read_served`
  (cogno-engram #76) and is checked when the access is built;
- **the sections in the tool description** (#12, grouped by document since #14):
  `describe_documents(docs, sections={doc_id: headings})`. `offer_consult_documents` passes none,
  because a heading is document CONTENT and filtering personal data out of it is the host's job;
- **the section heading as evidence** (#15, both directions since #17) needs no wiring: a passage
  under the hybrid floor passes when its heading and the question name each other, and
  `ConsultRecord.heading_match` counts them;
- **«did you mean…?» over a negative** (off by default): `DocumentsAccess(suggest_sections=True)`
  makes a *nothing relevant* reading record the section titles it cut that share a content word with the
  question, and adds an optional `section` argument to the schema that reads the one chosen.
  With it off, the schema, every payload and every record field are byte for byte what they
  were. The question a contact reads is the host's to write;
- **the documents an answer names** (0.1.1) needs no wiring either:
  `ConsultRecord.shown_documents` carries one `(document id, title)` pair per document the
  answer's text shows, so a host that wants to cite a source reads the record and never parses
  the text.

Since #17 the skill imports `cogno_anima.stages.scope_options` (the shared frame-word list). That
module exists from cogno-anima 0.1.1 on, and `pyproject.toml` says so: `cogno-anima>=0.1.1,<0.2`.

`web_search` and `web_fetch` are read-only and take everything that is policy from the host: the
search provider and its key, the allowance (raise `SearchQuotaExceeded`), the cache and its scope,
the record list. Wiring: [`docs/HOST_INTEGRATION.md`](docs/HOST_INTEGRATION.md) § 8; contract:
[`docs/WEB_TOOLS.md`](docs/WEB_TOOLS.md).

## What stays at the host

The concrete skills (shell/browser/...), the web search PROVIDER, shell/http/remote **providers**
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
pip install -e ".[dev,documents,web]"   # dev pulls cogno-engram (the skill tests use its real
                                        # store) and httpx (web_fetch runs against a local server)
pytest tests/unit -q            # fast, no network
pytest tests/integration -q     # real EGO over Ollama, auto-skips if absent; the Postgres
                                # leg needs CORTEX_TEST_PG_DSN naming a *test* database; the
                                # web_fetch leg starts its own local server (no network)
ruff check cogno_cortex tests examples && mypy cogno_cortex      # as CI runs them
python examples/host_min.py     # offline demo: discover → rank → bridge → execute
```

CI runs the unit suite under a coverage gate (`--cov=cogno_cortex --cov-fail-under=90`).

The library reads **no environment variable**. The one the repository reads is the tests':
`CORTEX_TEST_PG_DSN` (`tests/integration/test_consult_documents_postgres.py`).

## Documentation

Every `.md` of this repository.

- [`docs/HOST_INTEGRATION.md`](docs/HOST_INTEGRATION.md) — how a host wires cortex: the pieces,
  the per-turn flow, how a skill becomes a tool, custom providers, composing with MCP and native
  tools, feedback and metering, § 7, `consult_documents`, and § 8, the web skills.
- [`docs/CONSULT_DOCUMENTS.md`](docs/CONSULT_DOCUMENTS.md) — the full contract of the documents
  skill: the two gates, the description, the two fused searches, the floors and their one
  exception, reading a document whole, «did you mean…?» over a negative, what the executor reads,
  what a call spends, the record, and what stays with the host.
- [`docs/WEB_TOOLS.md`](docs/WEB_TOOLS.md) — the two web skills: the provider, the personal-data
  refusal, the fetch guards (SSRF and the rest), extraction, the cache, the record.
- [`LOGGING.md`](LOGGING.md) — what the library logs, at which level, and what a line never
  carries.
- [`examples/skills/math/SKILL.md`](examples/skills/math/SKILL.md) — the manifest of the example
  skill that `examples/host_min.py` discovers.
- [`CHANGELOG.md`](CHANGELOG.md) — every change, newest first.

Apache-2.0.
