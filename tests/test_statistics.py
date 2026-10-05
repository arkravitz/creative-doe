import numpy as np
import pytest

from creative_doe import Experiment, Metric
from creative_doe.design.matrix import Encoder
from creative_doe.diagnostics.identifiability import diagnose
from creative_doe.models.gaussian import GaussianShrinkage


def synthetic(n=160, seed=14, interaction=False):
    rng = np.random.default_rng(seed)
    e = Experiment(primary_metric=Metric("score", "continuous"))
    for key in ["a", "b"]:
        e.add_factor(key, [False, True])
    for run in range(n):
        a, b = (bool(v) for v in rng.integers(0, 2, 2))
        y = 1.2 * a + 0.8 * b + (1.1 * a * b if interaction else 0) + rng.normal(0, 0.25)
        e.observe({"a": a, "b": b}, value=y)
    return e


def test_main_effect_recovery():
    e = synthetic()
    records = e.effects()
    for rec, target in zip(records, [1.2, 0.8]):
        assert abs(rec["mean"] - target) < 0.15
        assert rec["identified"]
        assert rec["low"] < target < rec["high"]


def test_aliases_not_cured_by_prior():
    e = Experiment(primary_metric=Metric("y", "continuous"))
    for key in ["a", "b"]:
        e.add_factor(key, [False, True])
    for i in range(30):
        e.observe({"a": bool(i % 2), "b": bool(i % 2)}, value=i % 2)
    fit = e.fit()
    assert fit.diagnostics["rank"] < fit.diagnostics["columns"]
    assert all(not r["identified"] for r in e.effects())
    assert np.all(np.isfinite(fit.mean))
    assert fit.diagnostics["nullspace_relations"]


def test_non_pairwise_alias_detection():
    x = np.array([[1, 0, 0, 0], [1, 1, 0, 1], [1, 0, 1, 1], [1, 1, 1, 2.0]])
    d = diagnose(x, ["intercept", "a", "b", "a_plus_b"])
    assert d["rank"] == 3
    assert d["identifiable"]["intercept"]
    assert not d["identifiable"]["a"]


def test_matrix_reference_and_context():
    e = Experiment(primary_metric=Metric("y", "continuous"))
    e.add_factor("font", ["sans", "serif", "mono"])
    e.add_context("song", levels=["A", "B"])
    e.add_context("audience", kind="numeric", center=100, scale=10)
    enc = Encoder(e)
    np.testing.assert_allclose(
        enc.row({"font": "mono"}, {"song": "B", "audience": 120}, 31), [1, 0, 1, 1, 2, 1]
    )
    assert enc.row({}, {"song": "B", "audience": 120}, 31) is None


def test_conjugate_update_and_power_likelihood():
    e = synthetic(40)
    enc = Encoder(e)
    x, y, runs = enc.data(e, "score")
    model = GaussianShrinkage(half_life=10)
    p = model.fit(enc, x, y, runs, 40)
    w = 2 ** (-(40 - runs) / 10)
    assert p.shape == pytest.approx(2 + w.sum() / 2)
    assert p.weighted_posts < 40
    np.testing.assert_allclose(p.precision @ p.mean, x.T @ (w * y), atol=1e-9)
    assert p.scale > 0


def test_conditional_information_gain_equals_logdet():
    e = synthetic(20)
    p = e.fit()
    rec = e.recommend_next(1)[0]
    x = p.encoder.row(rec["configuration"], {}, 21)
    actual = 0.5 * (
        np.linalg.slogdet(p.precision + np.outer(x, x))[1] - np.linalg.slogdet(p.precision)[1]
    )
    assert rec["conditional_information_gain"] == pytest.approx(actual)


def test_interaction_gate_and_recovery():
    e = synthetic(200, interaction=True)
    assert ("a", "b") in e.interaction_candidates()
    e.enable_interaction("a", "b", rationale="Preplanned two-parent hypothesis")
    interaction = next(r for r in e.effects() if r["kind"] == "interaction")
    assert abs(interaction["mean"] - 1.1) < 0.25
    assert interaction["identified"]
    assert any("model selection" in w for w in e.fit().diagnostics["warnings"])


def test_interactions_rejected_without_evidence():
    e = synthetic(2)
    with pytest.raises(ValueError, match="heredity"):
        e.enable_interaction("a", "b", rationale="Too early")


def test_irrelevant_factor_sesoi():
    e = Experiment(primary_metric=Metric("y", "continuous"))
    e.add_factor("a", [False, True], sesoi=0.3)
    rng = np.random.default_rng(3)
    for i in range(200):
        e.observe({"a": bool(i % 2)}, value=rng.normal(0, 0.2))
    assert "review for retirement" in e.effects()[0]["interpretation"]
    assert e.factors["a"].status.value == "SCREENING"


def test_discounting_tracks_reversal_better():
    e = Experiment(primary_metric=Metric("y", "continuous"))
    e.add_factor("a", [False, True])
    rng = np.random.default_rng(4)
    for i in range(140):
        a = bool(rng.integers(2))
        e.observe({"a": a}, value=(1 if i < 80 else -1) * a + rng.normal(0, 0.15))
    stationary_error = abs(e.effects()[0]["mean"] + 1)
    e.model.half_life = 12
    assert abs(e.effects()[0]["mean"] + 1) < stationary_error
