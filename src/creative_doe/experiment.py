"""Public workflow and JSON persistence for evolving experiments."""

import csv
import io
import json
import re
from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path

from creative_doe.design.matrix import Encoder
from creative_doe.factors import Context, Factor, Status, validate_levels
from creative_doe.models.gaussian import GaussianShrinkage
from creative_doe.observations import Metric, Observation


def now():
    return datetime.now(UTC).isoformat()


def valid_id(value):
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", value):
        raise ValueError("IDs must start with a letter and contain letters, digits, or underscores")


class Experiment:
    def __init__(self, name="Creative experiment", primary_metric=None, seed=0, half_life=None):
        self.name = name
        primary = primary_metric or Metric()
        self.primary_metric = primary.name
        self.metrics = {primary.name: primary}
        self.seed = seed
        self.model = GaussianShrinkage(half_life=half_life)
        self.factors = {}
        self.contexts = {}
        self.schemas = []
        self._observations = []
        self.interactions = []
        self.interaction_events = []
        self._snapshot()

    @property
    def observations(self):
        # Neither caller-owned dictionaries nor returned records can mutate stored history.
        return tuple(deepcopy(self._observations))

    @property
    def next_run(self):
        return len(self._observations) + 1

    @property
    def schema_version(self):
        return len(self.schemas) - 1

    def _snapshot(self):
        self.schemas.append(
            {
                "version": len(self.schemas),
                "at_run": self.next_run,
                "timestamp": now(),
                "factors": {k: asdict(v) for k, v in self.factors.items()},
                "contexts": {k: asdict(v) for k, v in self.contexts.items()},
            }
        )

    def add_factor(
        self, id, levels, *, name=None, dtype="categorical", status=Status.SCREENING, sesoi=None
    ):
        valid_id(id)
        if id in self.factors or id in self.contexts:
            raise ValueError(f"ID already exists: {id}")
        if Status(status) == Status.RETIRED:
            raise ValueError("Introduce a factor before retiring it")
        f = Factor(
            id=id,
            name=name or id,
            levels=list(levels),
            dtype=dtype,
            status=status,
            introduced_run=self.next_run,
            sesoi=sesoi,
        )
        f.events.append(
            {
                "run": self.next_run,
                "timestamp": now(),
                "status": f.status.value,
                "rationale": "introduced",
            }
        )
        self.factors[id] = f
        self._snapshot()
        return deepcopy(f)

    def set_status(self, id, status, *, rationale, fixed_value=None):
        f = self.factors[id]
        target = Status(status)
        if not rationale.strip():
            raise ValueError("Record a rationale")
        allowed = {
            Status.PROPOSED: {Status.SCREENING},
            Status.SCREENING: {Status.ACTIVE, Status.RETIRED},
            Status.ACTIVE: {Status.RETIRED, Status.SCREENING},
            Status.RETIRED: {Status.SCREENING, Status.ACTIVE},
        }
        if target not in allowed[f.status]:
            raise ValueError(f"Invalid lifecycle transition {f.status.value} -> {target.value}")
        if target == Status.RETIRED:
            if fixed_value not in f.levels:
                raise ValueError("Retirement requires an explicit fixed_value from current levels")
            f.fixed_value = fixed_value
            f.retired_run = self.next_run
        else:
            f.fixed_value = None
            f.retired_run = None
        f.status, f.rationale = target, rationale
        f.events.append(
            {
                "run": self.next_run,
                "timestamp": now(),
                "status": target.value,
                "rationale": rationale,
                "fixed_value": f.fixed_value,
            }
        )
        self._snapshot()

    def retire_factor(
        self, id, *, fixed_value=None, rationale="Manual retirement; not a significance decision"
    ):
        # A deterministic explicit default is recorded in the schema and returned recommendations.
        value = self.factors[id].levels[0] if fixed_value is None else fixed_value
        self.set_status(id, Status.RETIRED, rationale=rationale, fixed_value=value)

    def reactivate_factor(self, id, *, rationale="New hypothesis"):
        self.set_status(id, Status.SCREENING, rationale=rationale)

    def update_levels(self, id, levels, *, rationale):
        f = self.factors[id]
        validate_levels(list(levels), f.dtype)
        if not rationale.strip():
            raise ValueError("Record a rationale")
        if f.status == Status.RETIRED and f.fixed_value not in levels:
            raise ValueError("Cannot remove the fixed level of a retired factor")
        f.levels = list(levels)
        f.events.append(
            {
                "run": self.next_run,
                "timestamp": now(),
                "levels": list(levels),
                "rationale": rationale,
            }
        )
        self._snapshot()

    def add_context(self, id, *, kind="categorical", levels=None, center=0.0, scale=1.0):
        valid_id(id)
        if id in self.contexts or id in self.factors:
            raise ValueError("ID already exists")
        self.contexts[id] = Context(id, kind, list(levels or []), center, scale)
        self._snapshot()

    def add_metric(self, name, kind="continuous", higher_is_better=True):
        if name in self.metrics:
            raise ValueError("Metric already exists")
        self.metrics[name] = Metric(name, kind, higher_is_better)

    def validate_configuration(self, configuration, schema_version=None, *, allow_unknown=False):
        version = self.schema_version if schema_version is None else schema_version
        if type(version) is not int or not 0 <= version < len(self.schemas):
            raise ValueError("Unknown schema version")
        schema = self.schemas[version]["factors"]
        if set(configuration) - set(schema):
            raise ValueError("Configuration contains factors unavailable in its schema")
        for key, f in schema.items():
            value = configuration.get(key)
            if f["status"] == "PROPOSED":
                if key in configuration:
                    raise ValueError("Proposed factors are not yet experimental variables")
                continue
            if value is None:
                if allow_unknown:
                    continue
                raise ValueError(
                    f"Missing value for {key}; explicitly record unknown observations with allow_unknown=True"
                )
            if value not in f["levels"]:
                raise ValueError(f"Invalid level for {key}: {value}")
            if f["status"] == "RETIRED" and value != f["fixed_value"]:
                raise ValueError(f"Retired factor {key} must remain at its fixed value")

    def observe(
        self,
        configuration,
        *,
        value=None,
        numerator=None,
        denominator=None,
        outcomes=None,
        context=None,
        schema_version=None,
        timestamp=None,
        provenance="manual",
        allow_unknown=False,
    ):
        version = self.schema_version if schema_version is None else schema_version
        self.validate_configuration(configuration, version, allow_unknown=allow_unknown)
        schema = self.schemas[version]
        ctx = context or {}
        if set(ctx) - set(schema["contexts"]):
            raise ValueError("Context unavailable in this schema")
        for key, val in ctx.items():
            if val is not None:
                Context(**schema["contexts"][key]).validate(val)
        if outcomes is None:
            result = (
                {"numerator": numerator, "denominator": denominator}
                if self.metrics[self.primary_metric].kind == "proportion"
                else {"value": value}
            )
            outcomes = {self.primary_metric: result}
        if not outcomes:
            raise ValueError("Provide at least one outcome")
        for metric, result in outcomes.items():
            if metric not in self.metrics:
                raise ValueError(f"Unknown metric {metric}")
            self.metrics[metric].transform(result)
        stamp = timestamp or now()
        datetime.fromisoformat(stamp)
        configuration = {
            key: configuration.get(key)
            for key, f in schema["factors"].items()
            if f["status"] != "PROPOSED"
        }
        obs = Observation(
            self.next_run,
            version,
            deepcopy(configuration),
            deepcopy(ctx),
            deepcopy(outcomes),
            stamp,
            provenance,
        )
        self._observations.append(obs)
        return deepcopy(obs)

    def fit(self, *, factor_ids=None, metric=None):
        name = metric or self.primary_metric
        if name not in self.metrics:
            raise ValueError("Unknown metric")
        encoder = Encoder(self, factor_ids)
        x, y, runs = encoder.data(self, name)
        posterior = self.model.fit(encoder, x, y, runs, self.next_run - 1)
        excluded = len(self._observations) - len(y)
        if excluded:
            posterior.diagnostics["warnings"].append(
                f"{excluded} posts excluded: unknown factors/context or missing metric. No historical values imputed."
            )
        posterior.diagnostics["warnings"].append(
            "Effects are conditional model contrasts, not automatically causal. Unmodeled interactions may alias main effects."
        )
        if self.interactions:
            posterior.diagnostics["warnings"].append(
                "Interactions were selected exploratorily; intervals do not account for model selection."
            )
        return posterior

    def effects(self, *, factor_ids=None, metric=None):
        fit = self.fit(factor_ids=factor_ids, metric=metric)
        lo, hi = fit.intervals()
        result = []
        for j, term in enumerate(fit.encoder.terms):
            if term.kind not in {"main", "interaction"}:
                continue
            identified = fit.diagnostics["identifiable"][term.name]
            sesoi = self.factors[term.parts[0][0]].sesoi if term.kind == "main" else None
            interpretation = "uncertain; gather more data"
            if not identified:
                interpretation = "not identified by data; prior-dependent"
            elif sesoi and lo[j] > -sesoi and hi[j] < sesoi:
                interpretation = "within SESOI under model; review for retirement"
            elif lo[j] > 0 or hi[j] < 0:
                interpretation = "worth investigating; exploratory evidence"
            result.append(
                {
                    "term": term.name,
                    "kind": term.kind,
                    "mean": float(fit.mean[j]),
                    "low": float(lo[j]),
                    "high": float(hi[j]),
                    "identified": identified,
                    "n_posts": fit.n_used,
                    "interpretation": interpretation,
                }
            )
        return result

    def interaction_candidates(self):
        fit = self.fit()
        lo, hi = fit.intervals()
        eligible = []
        for fid in fit.encoder.factor_ids:
            indices = [
                j
                for j, t in enumerate(fit.encoder.terms)
                if t.kind == "main" and t.parts[0][0] == fid
            ]
            if self.factors[fid].status not in {Status.ACTIVE, Status.SCREENING}:
                continue
            if (
                indices
                and all(fit.diagnostics["identifiable"][fit.encoder.names[j]] for j in indices)
                and any(lo[j] > 0 or hi[j] < 0 for j in indices)
            ):
                eligible.append(fid)
        return [
            tuple(pair)
            for pair in combinations(eligible, 2)
            if tuple(pair) not in self.interactions
        ]

    def enable_interaction(self, a, b, *, rationale):
        pair = next((p for p in self.interaction_candidates() if set(p) == {a, b}), None)
        if pair is None:
            raise ValueError(
                "Strong-heredity gate not met: both parent effects need identified exploratory evidence"
            )
        encoder = Encoder(self, interactions=self.interactions + [pair])
        x, _, _ = encoder.data(self, self.primary_metric)
        import numpy as np

        if len(x) < 2 * len(encoder.terms) or np.linalg.matrix_rank(x) < len(encoder.terms):
            raise ValueError(
                "Interaction expansion needs full-rank data and at least two posts per coefficient"
            )
        if not rationale.strip():
            raise ValueError("Record an interaction hypothesis")
        self.interactions.append(pair)
        self.interaction_events.append({"pair": pair, "run": self.next_run, "rationale": rationale})

    def recommend_next(self, n=4, **kwargs):
        from creative_doe.scheduler.greedy import recommend

        return recommend(self, n=n, **kwargs)

    def to_dict(self):
        return {
            "format_version": 1,
            "name": self.name,
            "primary_metric": self.primary_metric,
            "metrics": {k: asdict(v) for k, v in self.metrics.items()},
            "seed": self.seed,
            "model": asdict(self.model),
            "factors": {k: asdict(v) for k, v in self.factors.items()},
            "contexts": {k: asdict(v) for k, v in self.contexts.items()},
            "schemas": deepcopy(self.schemas),
            "observations": [asdict(o) for o in self._observations],
            "interactions": deepcopy(self.interactions),
            "interaction_events": deepcopy(self.interaction_events),
        }

    @classmethod
    def from_dict(cls, data):
        d = deepcopy(data)
        if d.get("format_version") != 1:
            raise ValueError("Unsupported persistence version")
        e = cls(d["name"], Metric(**d["metrics"][d["primary_metric"]]), d["seed"])
        e.metrics = {k: Metric(**v) for k, v in d["metrics"].items()}
        e.model = GaussianShrinkage(**d["model"])
        e.factors = {k: Factor(**v) for k, v in d["factors"].items()}
        e.contexts = {k: Context(**v) for k, v in d["contexts"].items()}
        e.schemas = d["schemas"]
        if not e.schemas or any(s["version"] != i for i, s in enumerate(e.schemas)):
            raise ValueError("Invalid schema history")
        e._observations = []
        for obs in d["observations"]:
            if obs["run"] != e.next_run:
                raise ValueError("Runs must be contiguous and ordered")
            e.observe(
                obs["configuration"],
                outcomes=obs["outcomes"],
                context=obs["context"],
                schema_version=obs["schema_version"],
                timestamp=obs["timestamp"],
                provenance=obs["provenance"],
                allow_unknown=True,
            )
        e.interactions = [tuple(p) for p in d["interactions"]]
        e.interaction_events = d.get("interaction_events", [])
        return e

    def save(self, path):
        path = Path(path)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(self.to_dict(), indent=2, allow_nan=False))
        temp.replace(path)

    @classmethod
    def load(cls, path):
        return cls.from_dict(json.loads(Path(path).read_text()))

    def export_csv(self):
        output = io.StringIO()
        fields = [
            "schema_version",
            "configuration",
            "context",
            "outcomes",
            "timestamp",
            "provenance",
        ]
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for obs in self._observations:
            row = {k: getattr(obs, k) for k in fields}
            for k in ["configuration", "context", "outcomes"]:
                row[k] = json.dumps(row[k])
            writer.writerow(row)
        return output.getvalue()

    def import_csv(self, text):
        # Transactional validation: a bad row cannot leave a half-imported experiment.
        candidate = Experiment.from_dict(self.to_dict())
        count = 0
        for row in csv.DictReader(io.StringIO(text)):
            candidate.observe(
                json.loads(row["configuration"]),
                context=json.loads(row["context"]),
                outcomes=json.loads(row["outcomes"]),
                schema_version=int(row["schema_version"]),
                timestamp=row["timestamp"],
                provenance=row.get("provenance") or "csv",
                allow_unknown=True,
            )
            count += 1
        self._observations = candidate._observations
        return count
