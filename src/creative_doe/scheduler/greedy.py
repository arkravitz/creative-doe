"""Finite-candidate sequential conditional D-gain with bounded feasibility backtracking."""

import math
from dataclasses import dataclass, field
from itertools import product

import numpy as np

from creative_doe.diagnostics.identifiability import diagnose
from creative_doe.factors import Status


class InfeasibleDesign(ValueError):
    pass


@dataclass
class Constraints:
    forbidden: list[dict] = field(default_factory=list)
    required: list[dict] = field(
        default_factory=list
    )  # Each pattern occurs at least once per batch.
    balance: list[str] = field(
        default_factory=list
    )  # Within-batch level counts differ by at most 1.
    max_changes: int | None = None
    baseline: dict | None = None
    cooldown: int = 0  # Do not repeat any of the previous k configurations.
    unique_batch: bool = True
    candidate_limit: int = 4096
    search_budget: int = 20000


def matches(config, pattern):
    return all(config.get(k) == v for k, v in pattern.items())


def candidates(experiment, constraints=None, finite_candidates=None):
    c = constraints or Constraints()
    if c.candidate_limit < 1 or c.search_budget < 1 or c.cooldown < 0:
        raise ValueError("Candidate/search limits must be positive; cooldown cannot be negative")
    factors = {k: f for k, f in experiment.factors.items() if f.status != Status.PROPOSED}
    for pattern in c.forbidden + c.required:
        if not pattern or any(
            k not in factors or v not in factors[k].levels for k, v in pattern.items()
        ):
            raise ValueError("Constraint pattern must use current factors and levels")
    if any(k not in factors or factors[k].status == Status.RETIRED for k in c.balance):
        raise ValueError("Balance requires manipulated factors")
    if c.max_changes is not None:
        if type(c.max_changes) is not int or c.max_changes < 0 or c.baseline is None:
            raise ValueError("max_changes requires a nonnegative integer and complete baseline")
        experiment.validate_configuration(c.baseline)
    if finite_candidates is None:
        domains = [
            [f.fixed_value] if f.status == Status.RETIRED else f.levels for f in factors.values()
        ]
        size = math.prod(map(len, domains))
        if size > c.candidate_limit:
            raise ValueError(
                f"{size} combinations exceed candidate_limit; supply a finite candidate subset"
            )
        pool = [dict(zip(factors, values)) for values in product(*domains)]
    else:
        pool = [dict(v) for v in finite_candidates]
        if len(pool) > c.candidate_limit:
            raise ValueError("Finite candidate subset exceeds candidate_limit")
        for config in pool:
            experiment.validate_configuration(config)
    valid = []
    for config in pool:
        if any(matches(config, p) for p in c.forbidden):
            continue
        if (
            c.max_changes is not None
            and sum(config[k] != c.baseline[k] for k in config) > c.max_changes
        ):
            continue
        if config not in valid:
            valid.append(config)
    if not valid:
        raise InfeasibleDesign("No feasible candidate configurations")
    return valid


