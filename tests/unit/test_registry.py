"""SkillRegistry: register/get/replace, ranking, feedback."""

from cogno_cortex import SkillManifest, SkillRegistry


def _reg(*manifests):
    r = SkillRegistry()
    for m in manifests:
        r.register(m)
    return r


def test_register_and_get(math_manifest):
    r = _reg(math_manifest)
    assert r.get("math") is math_manifest
    assert r.get("nope") is None
    assert r.skill_names() == ["math"]


def test_register_replaces_same_name():
    r = _reg(SkillManifest(name="x", priority=1))
    r.register(SkillManifest(name="x", priority=9))
    assert len(r.manifests) == 1
    assert r.get("x").priority == 9


def test_rank_direct_name_match(math_manifest):
    r = _reg(math_manifest, SkillManifest(name="search", tags=["web"]))
    assert r.rank(["math"]) == ["math"]


def test_rank_tag_overlap():
    r = _reg(SkillManifest(name="search", tags=["web", "lookup"]),
             SkillManifest(name="math", tags=["calculation"]))
    assert r.rank(["lookup"]) == ["search"]


def test_rank_strips_ner_prefix():
    r = _reg(SkillManifest(name="math", tags=["math"]))
    assert r.rank(["NER.MATH"]) == ["math"]


def test_rank_orders_by_score_then_priority():
    r = _reg(SkillManifest(name="a", tags=["t"], priority=1),
             SkillManifest(name="b", tags=["t"], priority=9))
    # same tag score → higher priority first
    assert r.rank(["t"]) == ["b", "a"]


def test_rank_respects_max_results():
    r = _reg(*[SkillManifest(name=f"s{i}", tags=["t"]) for i in range(5)])
    assert len(r.rank(["t"], max_results=2)) == 2


def test_rank_empty_when_no_match(math_manifest):
    assert _reg(math_manifest).rank(["unrelated"]) == []


def test_apply_feedback_nudges_rating():
    r = _reg(SkillManifest(name="x", performance_rating=0.5))
    r.apply_feedback("x", "good")
    assert abs(r.get("x").performance_rating - 0.6) < 1e-9
    r.apply_feedback("x", "bad")
    assert abs(r.get("x").performance_rating - 0.5) < 1e-9
    r.apply_feedback("x", "dangerous")
    assert abs(r.get("x").performance_rating - 0.2) < 1e-9
    r.apply_feedback("x", "weird")       # unknown feedback → no change
    assert abs(r.get("x").performance_rating - 0.2) < 1e-9
    r.apply_feedback("missing", "good")  # no-op, no crash
