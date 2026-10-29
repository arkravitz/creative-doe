"""Run: python examples/music_creator/demo.py"""

import json
from pathlib import Path

from creative_doe.scheduler import Constraints
from creative_doe.simulation.music import build_music_sample


def main():
    e, env = build_music_sample()
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
