"""Plot effect recovery on invented data with known coefficients.

Run from the repository root after installing the library and Matplotlib.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from creative_doe import Experiment, Metric

rng = np.random.default_rng(14)
experiment = Experiment(primary_metric=Metric("score", "continuous"))
experiment.add_factor("lyrics", [False, True])
experiment.add_factor("hook", [False, True])
for _ in range(160):
    lyrics, hook = (bool(v) for v in rng.integers(0, 2, 2))
    experiment.observe({"lyrics": lyrics, "hook": hook},
                       value=1.2 * lyrics + .8 * hook + rng.normal(0, .25))
effects = experiment.effects()
means = np.array([effect["mean"] for effect in effects])
low = np.array([effect["low"] for effect in effects])
high = np.array([effect["high"] for effect in effects])
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12})
fig, ax = plt.subplots(figsize=(9, 4.5), layout="constrained")
fig.set_facecolor("#faf9f6")
ax.set_facecolor("#faf9f6")
ax.errorbar(means, [1, 0], xerr=[means-low, high-means], fmt="o",
            color="#275d73", capsize=7, markersize=8, label="Estimate and 95% interval")
ax.scatter([1.2, .8], [1, 0], marker="|", s=350, color="#c35b36", label="Known generating effect")
ax.axvline(0, color="#cccccc", linestyle="--", linewidth=1)
ax.set_yticks([1, 0], ["Lyrics contrast", "Hook contrast"])
ax.set_xlim(0, 1.6)
ax.set_ylim(-.5, 1.7)
ax.set_xlabel("Conditional effect on synthetic score")
ax.set_title("Creative DOE: recovering known effects", loc="left", pad=18, fontweight="bold")
ax.legend(loc="upper left", frameon=False, fontsize=10)
ax.spines[["top", "right", "left"]].set_visible(False)
ax.grid(axis="x", alpha=.15)
fig.text(.02, -.02, "160 invented observations • generated coefficients 1.2 and 0.8 • no platform outcomes", fontsize=9)
output = Path(__file__).resolve().parents[2] / "docs/images/effect-recovery.png"
output.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(output, dpi=160, bbox_inches="tight")
print(output)
