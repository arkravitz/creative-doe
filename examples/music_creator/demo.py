"""Run: python examples/music_creator/demo.py"""

import json
from pathlib import Path

from creative_doe import Experiment
from creative_doe.scheduler import Constraints
from creative_doe.simulation.environment import SocialEnvironment


def main():
    e = Experiment("Music creator", seed=42)
    for key in ["lyrics", "hook", "font"]:
        e.add_factor(key, [False, True], dtype="boolean", sesoi=0.3)
    e.add_context("song", levels=["A", "B"])
    e.add_context("audience", kind="numeric", center=1)
    env = SocialEnvironment(seed=42, scenario="introduced")
    for run in range(1, 81):
        if run == 31:
            e.retire_factor(
                "font",
                fixed_value=False,
                rationale="Manual pause of font hypothesis; not proof of no effect",
            )
        if run == 47:
            e.add_factor("face", [False, True], dtype="boolean", sesoi=0.3)
        if run == 80:
            e.reactivate_factor("font", rationale="Revisit typography hypothesis")
        ctx = env.context(run)
        rec = e.recommend_next(1, contexts=[ctx])[0]
        outcome, _ = env.draw(rec["configuration"], run, ctx)
        e.observe(
            rec["configuration"],
            context=ctx,
            outcomes={"hold_rate": outcome},
            provenance="simulation",
        )
    output = Path("examples/music_creator/output")
    output.mkdir(parents=True, exist_ok=True)
    e.save(output / "experiment.json")
    (output / "observations.csv").write_text(e.export_csv())
    report = {
        "effects": e.effects(),
        "historical_effects": e.effects(factor_ids=["lyrics", "hook", "font"]),
        "diagnostics": e.fit().diagnostics,
        "recommendations": e.recommend_next(
            4,
            contexts=[env.context(r) for r in range(81, 85)],
            constraints=Constraints(balance=["face"]),
        ),
    }
    (output / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
