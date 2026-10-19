"""Generic, business-free skills that ship WITH the framework — each behind its own extra.

cortex is the framework, not the product's skills: what a persona can do for a business is the
host's catalog. What lives here is the rare skill that is pure MECHANISM — it knows no tenant, no
persona, no plan and no price, and takes everything that would be business as an injected
parameter. The rule a skill must satisfy to live here: every value that decides WHO may read
WHAT arrives from the caller, never from a default of this library and never from an argument
the model can fill.

Nothing in this package is imported by ``cogno_cortex/__init__``: ``import cogno_cortex`` must
keep working with none of these extras installed, and a test holds it (the import of a module
here is the moment its extra becomes a requirement).

* :mod:`cogno_cortex.skills.consult_documents` — search a ``cogno_engram.DocumentStore``
  (extra ``documents``).
* :mod:`cogno_cortex.skills.web_search` — search the public web through a ``SearchProvider`` the
  host injects (no extra: the provider, its key and its allowance are the host's).
* :mod:`cogno_cortex.skills.web_fetch` — download ONE public page, behind the SSRF and
  personal-data guards, and return its main text (extra ``web``).
"""
