"""Metrics keep their source counts; posts, not impressions, are analysis units."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Metric:
    name: str = "hold_rate"
    kind: str = "proportion"
    higher_is_better: bool = True

    def __post_init__(self):
        if self.kind not in {"proportion", "count", "continuous"}:
            raise ValueError("Metric kind must be proportion, count, or continuous")

    def transform(self, result: dict) -> float:
        if self.kind == "proportion":
            k, n = result.get("numerator"), result.get("denominator")
            if type(k) is not int or type(n) is not int or n <= 0 or not 0 <= k <= n:
                raise ValueError(
                    "Proportions require integer 0 <= numerator <= denominator, denominator > 0"
                )
            return math.log((k + 0.5) / (n - k + 0.5))
        y = result.get("value")
        if isinstance(y, bool) or not isinstance(y, (int, float)) or not math.isfinite(y):
            raise ValueError("Outcome value must be finite numeric")
        if self.kind == "count":
            if y < 0 or int(y) != y:
                raise ValueError("Counts must be nonnegative integers")
            return math.log1p(y)
        return float(y)


@dataclass(frozen=True)
class Observation:
    run: int
    schema_version: int
    configuration: dict
    context: dict
    outcomes: dict
    timestamp: str
    provenance: str = "manual"
