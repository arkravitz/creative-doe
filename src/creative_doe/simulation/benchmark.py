"""Reproducible comparisons of outcome and conditional effect learning, not causal validation."""

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from creative_doe import Experiment
from creative_doe.scheduler import candidates
from creative_doe.simulation.environment import SCENARIOS, SocialEnvironment


def run_trial(scenario="sparse", policy="adaptive", seed=0, runs=80):
    if policy not in {"adaptive", "random", "ofat"}:
        raise ValueError("Unknown policy")
    e = Experiment(scenario, seed=seed, half_life=20 if scenario == "drift" else None)
    for name in ["lyrics", "hook", "font"]:
        e.add_factor(name, [False, True], dtype="boolean", sesoi=0.3)
    e.add_context("song", levels=["A", "B"])
    e.add_context("audience", kind="numeric", center=1, scale=1)
    env = SocialEnvironment(seed + 1000, scenario)
    rng = np.random.default_rng(seed)
    cumulative = 0.0
    observed = 0.0
    for run in range(1, runs + 1):
        if scenario == "introduced" and run == runs // 2 + 1:
            e.add_factor("face", [False, True], dtype="boolean", sesoi=0.3)
        ctx = env.context(run)
        pool = candidates(e)
        if policy == "adaptive":
            config = e.recommend_next(1, contexts=[ctx], exploration=0.9)[0]["configuration"]
        elif policy == "random":
            config = pool[int(rng.integers(len(pool)))]
        else:
            keys = list(e.factors)
            # Repeated baseline-plus-one-factor cycle, unable to learn interactions.
            index = (run - 1) % (len(keys) + 1)
            config = {k: (index == i + 1) for i, k in enumerate(keys)}
        if scenario == "confounded":
            # Compliance failure: a creator changes lyrics to match song regardless of recommendation.
            config["lyrics"] = ctx["song"] == "B"
        result, p = env.draw(config, run, ctx)
        e.observe(config, context=ctx, outcomes={"hold_rate": result}, provenance=policy)
        cumulative += p
        observed += result["numerator"] / result["denominator"]
        if (
            scenario == "interactions"
            and run % 10 == 0
            and ("lyrics", "hook") in e.interaction_candidates()
        ):
            try:
                e.enable_interaction(
                    "lyrics", "hook", rationale="Simulator hypothesis; exploratory strong heredity"
                )
            except ValueError:
                pass
    records = e.effects()
    truth = env.effects(runs)
    errors, covered, identified = [], [], []
    # Reference-level conditional contrasts. When interaction is omitted this RMSE exposes bias.
    for record in records:
        if record["kind"] == "main":
            key = record["term"].split("[")[0]
            target = truth[key]
            errors.append((record["mean"] - target) ** 2)
            covered.append(record["low"] <= target <= record["high"])
            identified.append(record["identified"])
    fit = e.fit()
    interaction_record = next((r for r in records if r["kind"] == "interaction"), None)
    # Omitted interaction is a model prediction of zero, not an estimated or identified zero.
    interaction_error = (
        abs((interaction_record["mean"] if interaction_record else 0.0) - 1.0)
        if scenario == "interactions"
        else None
    )
    return {
        "scenario": scenario,
        "policy": policy,
        "seed": seed,
        "runs": runs,
        "cumulative_expected_hold": cumulative,
        "cumulative_observed_hold": observed,
        "main_effect_rmse": float(np.sqrt(np.mean(errors))),
        "interaction_absolute_error": interaction_error,
        "interval_coverage": float(np.mean(covered)),
        "identified_fraction": float(np.mean(identified)),
        "analysis_posts": fit.n_used,
        "enabled_interactions": len(e.interactions),
        "rank": fit.diagnostics["rank"],
        "columns": fit.diagnostics["columns"],
    }


def benchmark(seeds=5, runs=80, output="docs/benchmark_results"):
    rows = [
        run_trial(scenario, policy, seed, runs)
        for scenario in SCENARIOS
        for policy in ["adaptive", "random", "ofat"]
        for seed in range(seeds)
    ]
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = []
    for scenario in SCENARIOS:
        for policy in ["adaptive", "random", "ofat"]:
            subset = [r for r in rows if r["scenario"] == scenario and r["policy"] == policy]
            result = {"scenario": scenario, "policy": policy, "seeds": seeds}
            for key in [
                "cumulative_expected_hold",
                "main_effect_rmse",
                "interval_coverage",
                "identified_fraction",
                "enabled_interactions",
            ]:
                vals = [r[key] for r in subset]
                result[key] = float(np.mean(vals))
                result[key + "_sd"] = float(np.std(vals, ddof=1)) if seeds > 1 else 0.0
            interaction_errors = [
                r["interaction_absolute_error"]
                for r in subset
                if r["interaction_absolute_error"] is not None
            ]
            result["interaction_absolute_error"] = (
                float(np.mean(interaction_errors)) if interaction_errors else None
            )
            summary.append(result)
    path.with_suffix(".json").write_text(json.dumps(summary, indent=2))
    lines = [
        "# Simulation benchmark",
        "",
        f"{seeds} seeds per policy/scenario; {runs} posts each. Seed-level results in benchmark_results.csv.",
        "",
        "Reward is the sum of latent post hold probabilities, not impression totals. RMSE targets reference-level logit contrasts; drift targets the final effect. Coverage is descriptive, not calibrated validation. All intervals count, including prior-dependent aliases; identification is reported separately.",
        "",
        "| Scenario | Policy | Cumulative hold | Main-effect RMSE | Coverage | Identified |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in summary:
        lines.append(
            f"| {r['scenario']} | {r['policy']} | {r['cumulative_expected_hold']:.2f} ± {r['cumulative_expected_hold_sd']:.2f} | {r['main_effect_rmse']:.3f} ± {r['main_effect_rmse_sd']:.3f} | {r['interval_coverage']:.0%} | {r['identified_fraction']:.0%} |"
        )
    lines.extend(
        [
            "",
            "## Interaction learning",
            "",
            "| Policy | Interaction enabled | Mean absolute interaction error |",
            "|---|---:|---:|",
        ]
    )
    for result in summary:
        if result["scenario"] == "interactions":
            lines.append(
                f"| {result['policy']} | {result['enabled_interactions']:.0%} | {result['interaction_absolute_error']:.3f} |"
            )
    lines.append(
        "An omitted interaction counts as zero prediction when measuring error, not as evidence of a zero effect."
    )
    lines.extend(
        [
            "",
            "± is between-seed standard deviation, not a confidence interval. No policy dominance claim.",
            "",
            "Audience grows with time with an oscillating component so it can be distinguished from linear time. The confounded scenario overrides lyrics to match song for every policy, destroying identification. OFAT repeats baseline plus single changes, so it never observes the interaction cell. Interaction selection is attempted every ten runs; each method can fail its exploratory gate. The irrelevant-font scenario deliberately repeats sparse truth to check behavior with a null factor; it does not automatically retire factors. The D scheduler may keep sampling a well-estimated null factor to preserve contrast precision. No bandit baseline is included in v0.1.",
        ]
    )
    path.with_suffix(".md").write_text("\n".join(lines) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--runs", type=int, default=80)
    parser.add_argument("--output", default="docs/benchmark_results")
    args = parser.parse_args()
    if args.seeds < 1 or args.runs < 20:
        parser.error("Use at least one seed and twenty runs")
    summary = benchmark(args.seeds, args.runs, args.output)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
