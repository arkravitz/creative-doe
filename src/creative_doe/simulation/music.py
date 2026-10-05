"""A deterministic in-memory sample shared by the UI and CLI example."""

from creative_doe import Experiment
from creative_doe.simulation.environment import SocialEnvironment


def build_music_sample():
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
    return e, env
