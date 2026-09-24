# Logging in cogno-cortex

This library follows the Cogno house rule: **libraries emit, the host configures.**

- Each module does `logger = logging.getLogger(__name__)` and emits lazy
  `key=value` messages. The library installs **no** handlers/formatters and never
  calls `basicConfig`.
- The host attaches its handler and sets the level per package, e.g.
  `logging.getLogger("cogno_cortex").setLevel(logging.INFO)`.

## Level policy
- **ERROR** — never emitted. The bus raises `SkillNotFoundError` / `RuntimeError`
  (no provider); `CortexDispatcher` maps an unknown tool to a recoverable
  `ToolResult(ok=False)`. The host decides how to surface failures.
- **WARNING** — recoverable issues only: `event=skill_import_failed` when a skill
  `.py` fails to import (the loader skips it and continues);
  `event=consult_documents_embed_unavailable error=<ExceptionType|width>` when the
  question could not be embedded (the search degrades to words);
  `event=consult_documents_search_failed error=<ExceptionType>` when the document
  store raised (the tool answers with an error).
- **INFO** — none.
- **DEBUG** — `event=skill_invoked name=… provider=… status=…` per bus dispatch.

## What gets logged
- `cogno_cortex.bus` — DEBUG `event=skill_invoked`.
- `cogno_cortex.loader` — WARNING `event=skill_import_failed`.
- `cogno_cortex.skills.consult_documents` — the two WARNINGs above: an exception
  TYPE or a width, never the question, a title or a passage.
- `cogno_cortex.{types,base,registry,dispatcher}` — nothing.

Skill arguments, payloads and prompt bodies are **never** logged (only the skill
name, provider label, and status). Token usage rides on `SkillResult.usage`, not in
logs (metering is `cogno-meter`'s job).
