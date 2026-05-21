"""Hidden post-level logit environment, then binomial observation noise."""

from dataclasses import dataclass, field

import numpy as np
from scipy.special import expit

SCENARIOS = ("sparse", "interactions", "introduced", "irrelevant", "drift", "confounded")


@dataclass
class SocialEnvironment:
    seed: int = 0
    scenario: str = "sparse"
    noise: float = 0.45
    impressions: int = 1500
    rng: np.random.Generator = field(init=False, repr=False)

    def __post_init__(self):
        if self.scenario not in SCENARIOS:
            raise ValueError("Unknown scenario")
        self.rng = np.random.default_rng(self.seed)

    def effects(self, run):
        return {
            "lyrics": 0.9 if self.scenario != "drift" or run <= 40 else -0.7,
            "hook": 0.65,
            "font": 0.0,
            "face": 0.8 if self.scenario == "introduced" else 0.0,
        }

    def context(self, run):
        return {
            "song": "A" if run % 2 else "B",
            "audience": 1 + run / 100 + 0.15 * float(np.sin(run)),
        }

    def linear_predictor(self, config, run, context):
        effects = self.effects(run)
        eta = -1.0 + sum(effects.get(k, 0) * float(v) for k, v in config.items())
        eta += (0.8 if context["song"] == "B" else -0.4) + 0.2 * (context["audience"] - 1)
        eta += 0.06 * (run - 1) / 30
        if self.scenario == "interactions":
            eta += 1.0 * config["lyrics"] * config["hook"]
        return float(eta)

    def draw(self, config, run, context):
        p = float(
            expit(self.linear_predictor(config, run, context) + self.rng.normal(0, self.noise))
        )
        k = int(self.rng.binomial(self.impressions, p))
        return {"numerator": k, "denominator": self.impressions}, p
