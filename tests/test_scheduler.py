import pytest

from creative_doe import Experiment, Metric
from creative_doe.scheduler import Constraints, InfeasibleDesign, candidates


def setup():
    e = Experiment(primary_metric=Metric("y", "continuous"), seed=6)
    e.add_factor("a", [False, True])
    e.add_factor("b", [False, True])
    return e


def test_constraints_balance_required_forbidden():
    e = setup()
    recs = e.recommend_next(
        2,
        constraints=Constraints(
            forbidden=[{"a": True, "b": True}], required=[{"a": True}], balance=["a", "b"]
        ),
    )
    configs = [r["configuration"] for r in recs]
    assert {tuple(c.values()) for c in configs} == {(True, False), (False, True)}


def test_multilevel_balance_backtracking():
    e = setup()
    e.add_factor("font", ["a", "b", "c"])
    recs = e.recommend_next(4, constraints=Constraints(balance=["font", "a"]))
    counts = [sum(r["configuration"]["font"] == v for r in recs) for v in ["a", "b", "c"]]
    assert sorted(counts) == [1, 1, 2]


def test_impossible_batch_and_budget():
    e = setup()
    with pytest.raises(InfeasibleDesign):
        e.recommend_next(5)
    with pytest.raises(InfeasibleDesign):
        e.recommend_next(1, constraints=Constraints(required=[{"a": True}, {"a": False}]))
    with pytest.raises(InfeasibleDesign, match="budget"):
        e.recommend_next(2, constraints=Constraints(search_budget=1))


def test_max_changes_and_cooldown():
    e = setup()
    base = {"a": False, "b": False}
    e.observe(base, value=0)
    recs = e.recommend_next(2, constraints=Constraints(max_changes=1, baseline=base, cooldown=1))
    for r in recs:
        assert sum(r["configuration"].values()) == 1


def test_finite_candidate_set():
    e = setup()
    rec = e.recommend_next(1, finite_candidates=[{"a": False, "b": True}])[0]
    assert rec["configuration"] == {"a": False, "b": True}
    assert any("cannot identify" in w for w in rec["warnings"])
    with pytest.raises(ValueError):
        candidates(e, Constraints(candidate_limit=2))


def test_contexts_and_determinism():
    e = setup()
    e.add_context("song", levels=["A", "B"])
    ctx = [{"song": "A"}, {"song": "B"}]
    assert e.recommend_next(2, contexts=ctx) == e.recommend_next(2, contexts=ctx)
    assert [r["context"] for r in e.recommend_next(2, contexts=ctx)] == ctx
    with pytest.raises(ValueError):
        e.recommend_next(1)


def test_no_observation_side_effect_and_information_decreases():
    e = setup()
    recs = e.recommend_next(
        3, finite_candidates=[{"a": False, "b": False}], constraints=Constraints(unique_batch=False)
    )
    assert len(e.observations) == 0
    assert recs[-1]["conditional_information_gain"] < recs[0]["conditional_information_gain"]


def test_invalid_constraints():
    e = setup()
    with pytest.raises(ValueError):
        e.recommend_next(1, exploration=2)
    with pytest.raises(ValueError):
        candidates(e, Constraints(forbidden=[{"typo": True}]))
    with pytest.raises(ValueError):
        candidates(e, Constraints(max_changes=1))


def test_new_factor_gets_crossed_without_inventing_old_values():
    e = setup()
    for i in range(40):
        e.observe({"a": bool(i % 2), "b": bool((i // 2) % 2)}, value=float(i % 2))
    e.add_factor("face", [False, True])
    recs = e.recommend_next(4, constraints=Constraints(balance=["face"]))
    assert sum(r["configuration"]["face"] for r in recs) == 2
    assert all(any("face, observed in only 0" in reason for reason in r["reasons"]) for r in recs)
    assert e.fit().n_used == 0
    assert e.fit(factor_ids=["a", "b"]).n_used == 40
