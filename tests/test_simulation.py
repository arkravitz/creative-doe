import pytest

from creative_doe.simulation.benchmark import run_trial
from creative_doe.simulation.environment import SCENARIOS


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_simulation_scenarios(scenario):
    result = run_trial(scenario, "adaptive", seed=12, runs=60)
    assert 0 < result["cumulative_expected_hold"] < 60
    if scenario == "confounded":
        assert result["identified_fraction"] < 1
    elif scenario == "introduced":
        assert result["analysis_posts"] == 30
    elif scenario in {"sparse", "irrelevant"}:
        assert result["main_effect_rmse"] < 0.4


def test_reproducibility():
    assert run_trial("sparse", "random", 7, 24) == run_trial("sparse", "random", 7, 24)
