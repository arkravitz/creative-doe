"""Normal-inverse-gamma ridge regression with optional power-likelihood forgetting."""

from dataclasses import dataclass
from typing import Protocol

import numpy as np
from scipy.stats import t

from creative_doe.diagnostics.identifiability import diagnose


class RegressionModel(Protocol):
    def fit(self, encoder, x, y, runs, current_run): ...


@dataclass
class Posterior:
    encoder: object
    mean: np.ndarray
    precision: np.ndarray
    covariance_scale: np.ndarray
    shape: float
    scale: float
    diagnostics: dict
    n_used: int
    weighted_posts: float
    kish_effective_posts: float

    def intervals(self):
        sd = np.sqrt(np.diag(self.covariance_scale) * self.scale / self.shape)
        radius = t.ppf(0.975, 2 * self.shape) * sd
        return self.mean - radius, self.mean + radius

    def predict(self, row):
        mu = float(row @ self.mean)
        predictive_scale = np.sqrt(
            self.scale / self.shape * (1 + row @ self.covariance_scale @ row)
        )
        radius = float(t.ppf(0.975, 2 * self.shape) * predictive_scale)
        return {
            "mean_transformed": mu,
            "predictive_low": mu - radius,
            "predictive_high": mu + radius,
        }


@dataclass
class GaussianShrinkage:
    half_life: float | None = None
    main_scale: float = 1.5
    interaction_scale: float = 0.75
    noise_shape: float = 2.0
    noise_scale: float = 1.0

    def __post_init__(self):
        for value in [self.main_scale, self.interaction_scale, self.noise_shape, self.noise_scale]:
            if not np.isfinite(value) or value <= 0:
                raise ValueError("Prior parameters must be positive and finite")
        if self.half_life is not None and (not np.isfinite(self.half_life) or self.half_life <= 0):
            raise ValueError("half_life must be positive and finite")

    def fit(self, encoder, x, y, runs, current_run):
        scales = {
            "intercept": 10.0,
            "main": self.main_scale,
            "interaction": self.interaction_scale,
            "context": 2.0,
            "numeric_context": 2.0,
            "time": 2.0,
        }
        prior = np.diag([1 / scales[term.kind] ** 2 for term in encoder.terms])
        w = (
            np.ones(len(y))
            if self.half_life is None
            else 2.0 ** (-(current_run - runs) / self.half_life)
        )
        precision = prior + x.T @ (w[:, None] * x)
        inv = np.linalg.solve(precision, np.eye(len(prior)))
        mean = np.linalg.solve(precision, x.T @ (w * y))
        shape = self.noise_shape + w.sum() / 2
        # Stable residual form avoids subtracting near-equal quadratic forms.
        scale = self.noise_scale + ((w * (y - x @ mean) ** 2).sum() + mean @ prior @ mean) / 2
        diagnostic = diagnose(x, encoder.names, w)
        if self.half_life is not None:
            diagnostic["warnings"].append(
                "Temporal discounting is a generalized/power posterior, not a fitted drift model."
            )
        return Posterior(
            encoder,
            mean,
            precision,
            inv,
            float(shape),
            float(scale),
            diagnostic,
            len(y),
            float(w.sum()),
            float(w.sum() ** 2 / (w @ w)) if len(w) else 0.0,
        )
