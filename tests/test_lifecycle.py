import json

import pytest

from creative_doe import Experiment, Metric, Status
from creative_doe.design.matrix import Encoder


def experiment():
    e = Experiment(primary_metric=Metric("score", "continuous"))
    e.add_factor("lyrics", [False, True], dtype="boolean")
    return e


def test_factor_creation_and_proposed():
    e = experiment()
    e.add_factor("font", ["sans", "serif"], status=Status.PROPOSED)
    assert "font" not in e.recommend_next(1)[0]["configuration"]
    e.set_status("font", Status.SCREENING, rationale="Ready")
    assert "font" in e.recommend_next(1)[0]["configuration"]


@pytest.mark.parametrize(
    "levels,dtype",
    [
        ([1, 1], "numeric"),
        ([None, "x"], "categorical"),
        ([False, 1], "boolean"),
        ([0, float("nan")], "numeric"),
        (["only"], "categorical"),
        ([{}, {}], "categorical"),
    ],
)
def test_invalid_factors(levels, dtype):
    with pytest.raises(ValueError):
        Experiment().add_factor("factor", levels, dtype=dtype)


def test_new_factor_does_not_rewrite_history():
    e = experiment()
    obs = e.observe({"lyrics": False}, value=1)
    old_schema = json.dumps(e.schemas)
    e.add_factor("face", [False, True])
    e.observe({"lyrics": True, "face": True}, value=2)
    assert "face" not in e.observations[0].configuration
    assert e.schemas[obs.schema_version]["factors"].keys() == {"lyrics"}
    assert e.fit().n_used == 1
    assert e.fit(factor_ids=["lyrics"]).n_used == 2
    assert old_schema == json.dumps(e.schemas[:-1])


def test_retire_reactivate_and_level_changes():
    e = experiment()
    e.observe({"lyrics": True}, value=2)
    e.retire_factor("lyrics", fixed_value=False)
    assert e.recommend_next(1)[0]["configuration"] == {"lyrics": False}
    e.reactivate_factor("lyrics")
    assert e.factors["lyrics"].status == Status.SCREENING
    assert len(e.factors["lyrics"].events) == 3
    e.add_factor("font", ["sans", "serif"])
    e.observe({"lyrics": False, "font": "serif"}, value=0)
    e.update_levels("font", ["sans", "mono"], rationale="New typography")
    assert e.observations[-1].configuration["font"] == "serif"
    assert Encoder(e).domains["font"] == ["sans", "serif", "mono"]
    assert e.fit().n_used == 1  # The pre-font run remains unavailable.


@pytest.mark.parametrize("config", [{}, {"lyrics": "yes"}, {"lyrics": False, "unknown": 1}])
def test_invalid_configuration(config):
    with pytest.raises(ValueError):
        experiment().observe(config, value=1)


def test_unknown_is_not_reference_level():
    e = experiment()
    e.observe({"lyrics": None}, value=1, allow_unknown=True)
    assert e.observations[0].configuration["lyrics"] is None
    assert e.fit().n_used == 0
    assert e.fit().diagnostics["rank"] == 0


def test_observation_isolation():
    e = experiment()
    cfg = {"lyrics": True}
    obs = e.observe(cfg, value=1)
    cfg["lyrics"] = False
    obs.configuration["lyrics"] = False
    e.observations[0].configuration["lyrics"] = False
    assert e.observations[0].configuration["lyrics"] is True


def test_roundtrip_and_schema_validation(tmp_path):
    e = experiment()
    e.observe({"lyrics": True}, value=1)
    e.retire_factor("lyrics")
    path = tmp_path / "experiment.json"
    e.save(path)
    loaded = Experiment.load(path)
    assert loaded.to_dict() == e.to_dict()
    assert loaded.recommend_next(1) == e.recommend_next(1)
    data = e.to_dict()
    data["observations"][0]["configuration"]["lyrics"] = "invalid"
    with pytest.raises(ValueError):
        Experiment.from_dict(data)


def test_csv_roundtrip_and_atomic_import():
    e = experiment()
    e.observe({"lyrics": True}, value=1)
    clone = experiment()
    assert clone.import_csv(e.export_csv()) == 1
    assert clone.observations[0].outcomes == e.observations[0].outcomes
    text = e.export_csv() + "bad,row\n"
    with pytest.raises((ValueError, TypeError, KeyError)):
        clone.import_csv(text)
    assert len(clone.observations) == 1


def test_old_schema_result_and_added_context():
    e = experiment()
    old = e.schema_version
    e.add_factor("face", [False, True])
    e.add_context("song", levels=["A", "B"])
    e.observe({"lyrics": False}, value=2, schema_version=old)
    assert e.fit().n_used == 0
    assert "face" not in e.observations[0].configuration


def test_multi_metric_preserves_counts():
    e = experiment()
    e.add_metric("hold", "proportion")
    e.observe(
        {"lyrics": True},
        outcomes={"score": {"value": 3}, "hold": {"numerator": 0, "denominator": 100}},
    )
    assert e.fit(metric="hold").n_used == 1
    assert e.observations[0].outcomes["hold"]["denominator"] == 100


@pytest.mark.parametrize(
    "result",
    [
        {"numerator": 1, "denominator": 0},
        {"numerator": 2, "denominator": 1},
        {"numerator": -1, "denominator": 10},
        {"numerator": 1.2, "denominator": 10},
    ],
)
def test_invalid_proportions(result):
    with pytest.raises(ValueError):
        Metric().transform(result)
