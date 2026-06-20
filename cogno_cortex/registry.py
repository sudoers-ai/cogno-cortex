"""``SkillRegistry`` — tag-based skill matching and ranking (pure, no I/O).

Ranks registered manifests against NER-extracted tags (domains + mandatory_tags +
intent hints) so the host can pick the most relevant skills to expose to the EGO.
Ported from the parent ``cogno.skills.registry``.
"""

from __future__ import annotations

from typing import Optional

from cogno_cortex.types import SkillManifest


class SkillRegistry:
    """Holds ``SkillManifest``s and ranks them by tag overlap.

    Ranking (descending): direct name match (+100) → tag overlap (+10 each) →
    tie-break by (priority, performance_rating).
    """

    def __init__(self) -> None:
        self._manifests: list[SkillManifest] = []

    def register(self, manifest: SkillManifest) -> None:
        # replace an existing manifest of the same name (idempotent re-register)
        self._manifests = [m for m in self._manifests if m.name != manifest.name]
        self._manifests.append(manifest)

    def get(self, name: str) -> Optional[SkillManifest]:
        for m in self._manifests:
            if m.name == name:
                return m
        return None

    @property
    def manifests(self) -> list[SkillManifest]:
        return list(self._manifests)

    def skill_names(self) -> list[str]:
        return [m.name for m in self._manifests]

    @staticmethod
    def _normalize_tags(tags: list[str]) -> set[str]:
        """Lowercase + strip a ``NER.`` prefix (NER emits ``NER.MATH`` → ``math``)."""
        out: set[str] = set()
        for tag in tags:
            low = tag.lower()
            out.add(low)
            if low.startswith("ner."):
                out.add(low[4:])
        return out

    def rank(self, tags: list[str], *, max_results: int = 3) -> list[str]:
        """Return up to ``max_results`` skill names ordered by relevance to ``tags``."""
        tags_set = self._normalize_tags(tags)
        scored: list[tuple[tuple[int, int, float], SkillManifest]] = []
        for m in self._manifests:
            score = 0
            if m.name.lower() in tags_set:
                score += 100
            overlap = {t.lower() for t in m.tags} & tags_set
            score += len(overlap) * 10
            if score > 0:
                scored.append(((score, m.priority, m.performance_rating), m))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m.name for _, m in scored[:max_results]]

    def apply_feedback(self, skill_name: str, feedback: str) -> None:
        """Nudge a skill's ``performance_rating`` from execution feedback.

        ``good`` → +0.1, ``bad`` → −0.1, ``dangerous`` → −0.3 (clamped to [0,1]).
        """
        m = self.get(skill_name)
        if m is None:
            return
        fb = feedback.lower()
        if fb == "good":
            m.performance_rating = min(1.0, m.performance_rating + 0.1)
        elif fb == "bad":
            m.performance_rating = max(0.0, m.performance_rating - 0.1)
        elif fb == "dangerous":
            m.performance_rating = max(0.0, m.performance_rating - 0.3)
