# v0.1 validation record

Executed locally on 2026-09-11 using Python 3.12.8, NumPy 2.5.3, SciPy 1.18.1,
Streamlit 1.63.0, pytest 9.1.1, and setuptools 84.0.0. Exact installed dependency
versions are in `requirements-tested.txt`. The CI matrix is configured but has not
been executed on GitHub.

- `pytest -q`: **49 passed in 2.92s**. Includes real Streamlit AppTest workflow:
  add a factor, record counts, request a batch, inspect returned recommendations.
- `ruff check src tests app examples`: **All checks passed**.
- `uv build --no-build-isolation --offline`: built source archive and pure-Python wheel.
- `python examples/music_creator/demo.py`: completed all 80 posts and exported JSON,
  CSV, effect diagnostics, and the next four recommendations.
- `python -m creative_doe.simulation.benchmark --seeds 10 --runs 80`: completed
  180 policy/scenario/seed trials, totaling 14,400 simulated posts.
- Streamlit server started successfully on `127.0.0.1:8501`. UI behavior was exercised
  with AppTest; no separate visual browser screenshot audit was performed.

## Checks that matter statistically

Tests verify conjugate normal equations and weighted variance shape updates;
conditional information gain against a log-determinant calculation; non-pairwise
null-space aliases; separation of proper posterior estimates from likelihood
identification; main and interaction recovery; missing history and retained sample
counts; temporal reversal tracking; and reproducible simulations. Lifecycle, finite
candidate constraints, JSON round trips, and transactional CSV validation are covered.

The music example retires font at 31, adds face at 47, and reactivates font at 80.
The final full model uses 34 posts. The older-factor model uses 80. This is intentional,
not a claim that earlier posts reveal face values. Both model reports are saved in
`examples/music_creator/output/report.json`.

## Observed compromises and boundaries

Early recovery tests showed strong interaction attenuation under a conditional prior
scale of 0.35 residual standard deviations. Defaults were widened to 1.5 for main
contrasts and 0.75 for interactions. This is documented development tuning; the same
simulator is not an independent confirmatory evaluation.

The ten-seed results do not establish policy dominance. Random sampling slightly
outperforms adaptive design on sparse stationary main-effect RMSE. Adaptive design
has lower RMSE for introduced factors and drifting effects in this run, while usually
accepting lower cumulative reward. Both cross-factor methods enable the simulated
interaction in all ten seeds; OFAT never identifies it. See `benchmark_results.md`
for full numbers and limitations, including why apparently accurate aliased estimates
must not be interpreted as identified effects.

## UI redesign follow-up

The creator workspace was redesigned with a warm visual theme, focused sidebar
navigation, choice cards, native option/count inputs, downloadable creative briefs,
recommendation-to-result prefilling, visual effect intervals, and responsive mobile
navigation. Ordinary workflows no longer require JSON editing.

Validation after the redesign:

- `pytest -q`: **54 passed in 4.56s**, including six UI workflow tests.
- `ruff check src tests app examples`: **All checks passed**.
- The 80-post music example completed again without engine changes.
- Source and wheel builds succeeded; the source archive includes the stylesheet,
  Streamlit theme, and simulated example used by the UI.
- Actual Chromium browser flow passed: music starter → custom choice dialog → batch
  generation → prefilled results → count entry → effect chart.
- Desktop (1440px) and mobile (390px) screenshots were inspected. No horizontal
  overflow or browser page errors were observed. Mobile “Go to” navigation passed.
- Dialog lifecycle, pause actions, invalid empty outcomes, old-schema observations,
  planned contexts at different batch sizes, and simulated-data labeling are covered
  by Streamlit AppTest.

The Python statistical engine remains unchanged. The optional UI now requires
Streamlit 1.63+ for its tested dialog and input behavior.
