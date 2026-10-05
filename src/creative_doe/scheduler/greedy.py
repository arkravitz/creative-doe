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


def recommend(
    experiment,
    n=4,
    *,
    exploration=1.0,
    constraints=None,
    contexts=None,
    finite_candidates=None,
    seed=None,
):
    if type(n) is not int or n < 1:
        raise ValueError("n must be a positive integer")
    if not np.isfinite(exploration) or not 0 <= exploration <= 1:
        raise ValueError("exploration must be between 0 and 1")
    c = constraints or Constraints()
    pool = candidates(experiment, c, finite_candidates)
    if contexts is None:
        contexts = [{} for _ in range(n)]
    if len(contexts) != n:
        raise ValueError("Supply one observed/planned context per upcoming post")
    for ctx in contexts:
        if set(ctx) != set(experiment.contexts):
            raise ValueError("Provide every contextual/blocking variable for each planned post")
        for k, v in ctx.items():
            experiment.contexts[k].validate(v)
    fit = experiment.fit()
    rows = np.asarray(
        [
            [fit.encoder.row(config, ctx, experiment.next_run + slot) for config in pool]
            for slot, ctx in enumerate(contexts)
        ]
    )
    if rows.dtype == object:
        raise ValueError("Candidates have unknown modeled values")
    x, _, _ = fit.encoder.data(experiment, experiment.primary_metric)
    possible = diagnose(np.vstack([x, rows.reshape(-1, rows.shape[-1])]), fit.encoder.names)
    warnings = list(fit.diagnostics["warnings"])
    if possible["rank"] < possible["columns"]:
        warnings.append(
            "Even the feasible candidate set cannot identify all current coefficients; revise constraints/model."
        )
    rng = np.random.default_rng(experiment.seed + experiment.next_run if seed is None else seed)
    tie = rng.random((n, len(pool))) * 1e-10
    history = [o.configuration for o in experiment.observations]
    direction = 1 if experiment.metrics[experiment.primary_metric].higher_is_better else -1
    nodes = 0

    def search(selected, covariance, details):
        nonlocal nodes
        nodes += 1
        if nodes > c.search_budget:
            raise InfeasibleDesign(
                "Feasibility search budget exhausted; simplify constraints or increase search_budget"
            )
        slot = len(selected)
        configs = [pool[j] for j in selected]
        missing = [p for p in c.required if not any(matches(cfg, p) for cfg in configs)]
        if slot == n:
            balanced = all(
                max(counts(k, configs)) - min(counts(k, configs)) <= 1 for k in c.balance
            )
            return details if not missing and balanced else None
        remaining = n - slot
        if any(not any(matches(cfg, p) for cfg in pool) for p in missing):
            return None
        if any(
            sum(max(0, n // len(experiment.factors[k].levels) - v) for v in counts(k, configs))
            > remaining
            for k in c.balance
        ):
            return None
        slot_rows = rows[slot]
        gain = 0.5 * np.log1p(np.einsum("ij,jk,ik->i", slot_rows, covariance, slot_rows))
        predictions = direction * (slot_rows @ fit.mean)

        def normalize(values):
            span = np.ptp(values)
            return (values - np.min(values)) / span if span > 1e-12 else np.zeros_like(values)

        scores = (
            exploration * normalize(gain) + (1 - exploration) * normalize(predictions) + tie[slot]
        )
        for j in np.argsort(-scores):
            config = pool[j]
            if c.unique_batch and j in selected:
                continue
            if c.cooldown and config in (history + configs)[-c.cooldown :]:
                continue
            if any(
                counts(k, configs + [config]).count(
                    math.ceil(n / len(experiment.factors[k].levels)) + 1
                )
                for k in c.balance
            ):
                continue
            if remaining == 1 and any(not matches(config, p) for p in missing):
                continue
            row = slot_rows[j]
            v = covariance @ row
            updated = covariance - np.outer(v, v) / (1 + row @ v)
            detail = (int(j), float(gain[j]), row)
            result = search(selected + [int(j)], updated, details + [detail])
            if result is not None:
                return result
        return None

    def counts(key, configs):
        return [
            sum(cfg[key] == level for cfg in configs) for level in experiment.factors[key].levels
        ]

    selected = search([], fit.covariance_scale.copy(), [])
    if selected is None:
        raise InfeasibleDesign(
            "No batch satisfies all hard constraints; no constraints were relaxed"
        )
    result = []
    for slot, (j, gain, row) in enumerate(selected):
        config = pool[j]
        reasons = [
            f"Conditional Gaussian coefficient information gain: {gain:.3f} nats (given residual variance).",
            f"Learning weight {exploration:.0%}; reward uses predicted transformed {experiment.primary_metric}.",
        ]
        for key, f in experiment.factors.items():
            if f.status in {Status.ACTIVE, Status.SCREENING}:
                known = sum(o.configuration.get(key) is not None for o in experiment.observations)
                if known < 10:
                    reasons.append(f"Explores {key}, observed in only {known} historical posts.")
        if c.balance:
            reasons.append("Enforces within-batch balance for " + ", ".join(c.balance) + ".")
        reasons.append(
            "Joint covariance scoring targets uncertain directions; inspect alias warnings before interpretation."
        )
        result.append(
            {
                "run": experiment.next_run + slot,
                "schema_version": experiment.schema_version,
                "configuration": config,
                "context": contexts[slot],
                "prediction": fit.predict(row),
                "conditional_information_gain": gain,
                "reasons": reasons,
                "warnings": warnings,
            }
        )
    return result
