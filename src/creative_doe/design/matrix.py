"""Stable reference coding using the union of historical domains, never missing-as-zero."""

from dataclasses import dataclass
from itertools import product

import numpy as np


@dataclass(frozen=True)
class Term:
    name: str
    parts: tuple[tuple[str, object], ...]
    kind: str


class Encoder:
    def __init__(self, experiment, factor_ids=None, interactions=None):
        self.factor_ids = (
            list(factor_ids)
            if factor_ids is not None
            else [
                k
                for k, f in experiment.factors.items()
                if any(
                    s["factors"].get(k, {}).get("status") in {"SCREENING", "ACTIVE", "RETIRED"}
                    for s in experiment.schemas
                )
            ]
        )
        if len(set(self.factor_ids)) != len(self.factor_ids) or any(
            k not in experiment.factors for k in self.factor_ids
        ):
            raise ValueError("Unknown or duplicate analysis factors")
        self.contexts = experiment.contexts
        self.domains = {}
        self.terms = [Term("intercept", (), "intercept")]
        for fid in self.factor_ids:
            levels = []
            for s in experiment.schemas:
                for level in s["factors"].get(fid, {}).get("levels", []):
                    if level not in levels:
                        levels.append(level)
            self.domains[fid] = levels
            self.terms.extend(Term(f"{fid}[{v!r}]", ((fid, v),), "main") for v in levels[1:])
        for a, b in experiment.interactions if interactions is None else interactions:
            if a in self.domains and b in self.domains:
                self.terms.extend(
                    Term(f"{a}[{u!r}]:{b}[{v!r}]", ((a, u), (b, v)), "interaction")
                    for u, v in product(self.domains[a][1:], self.domains[b][1:])
                )
        for cid, c in self.contexts.items():
            if c.kind == "numeric":
                self.terms.append(Term(f"context:{cid}", ((cid, None),), "numeric_context"))
            else:
                self.terms.extend(
                    Term(f"context:{cid}[{v!r}]", ((cid, v),), "context") for v in c.levels[1:]
                )
        self.terms.append(Term("time_per_30_runs", (), "time"))
        self.names = [t.name for t in self.terms]

    def row(self, configuration, context, run):
        if any(configuration.get(k) is None for k in self.factor_ids):
            return None
        if any(context.get(k) is None for k in self.contexts):
            return None
        for k in self.factor_ids:
            if configuration[k] not in self.domains[k]:
                raise ValueError(f"Unknown analysis level for {k}")
        for k, c in self.contexts.items():
            c.validate(context[k])
        row = []
        for t in self.terms:
            if t.kind == "intercept":
                row.append(1.0)
            elif t.kind == "time":
                row.append((run - 1) / 30)
            elif t.kind == "numeric_context":
                key = t.parts[0][0]
                c = self.contexts[key]
                row.append((context[key] - c.center) / c.scale)
            elif t.kind == "context":
                key, level = t.parts[0]
                row.append(float(context[key] == level))
            else:
                row.append(float(all(configuration[k] == v for k, v in t.parts)))
        return np.asarray(row)

    def data(self, experiment, metric):
        rows, y, runs = [], [], []
        for obs in experiment.observations:
            if metric not in obs.outcomes:
                continue
            row = self.row(obs.configuration, obs.context, obs.run)
            if row is not None:
                rows.append(row)
                y.append(experiment.metrics[metric].transform(obs.outcomes[metric]))
                runs.append(obs.run)
        return (np.asarray(rows).reshape(-1, len(self.terms)), np.asarray(y), np.asarray(runs))
