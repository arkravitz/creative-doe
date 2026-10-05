# Simulation benchmark

10 seeds per policy/scenario; 80 posts each. Seed-level results in benchmark_results.csv.

Reward is the sum of latent post hold probabilities, not impression totals. RMSE targets reference-level logit contrasts; drift targets the final effect. Coverage is descriptive, not calibrated validation. All intervals count, including prior-dependent aliases; identification is reported separately.

| Scenario | Policy | Cumulative hold | Main-effect RMSE | Coverage | Identified |
|---|---|---:|---:|---:|---:|
| sparse | adaptive | 42.03 ± 0.97 | 0.112 ± 0.045 | 90% | 100% |
| sparse | random | 42.41 ± 1.90 | 0.104 ± 0.048 | 93% | 100% |
| sparse | ofat | 35.18 ± 0.75 | 0.122 ± 0.050 | 97% | 33% |
| interactions | adaptive | 45.61 ± 1.17 | 0.131 ± 0.051 | 97% | 100% |
| interactions | random | 45.91 ± 2.20 | 0.129 ± 0.050 | 93% | 100% |
| interactions | ofat | 35.18 ± 0.75 | 0.122 ± 0.050 | 97% | 33% |
| introduced | adaptive | 44.84 ± 0.65 | 0.130 ± 0.037 | 95% | 100% |
| introduced | random | 45.68 ± 2.08 | 0.154 ± 0.055 | 90% | 100% |
| introduced | ofat | 35.98 ± 0.86 | 0.171 ± 0.060 | 100% | 100% |
| irrelevant | adaptive | 42.03 ± 0.97 | 0.112 ± 0.045 | 90% | 100% |
| irrelevant | random | 42.41 ± 1.90 | 0.104 ± 0.048 | 93% | 100% |
| irrelevant | ofat | 35.18 ± 0.75 | 0.122 ± 0.050 | 97% | 33% |
| drift | adaptive | 35.09 ± 0.73 | 0.215 ± 0.058 | 93% | 100% |
| drift | random | 35.82 ± 1.63 | 0.245 ± 0.071 | 87% | 100% |
| drift | ofat | 31.56 ± 0.82 | 0.491 ± 0.028 | 100% | 33% |
| confounded | adaptive | 44.46 ± 0.64 | 0.136 ± 0.036 | 97% | 67% |
| confounded | random | 41.98 ± 1.27 | 0.115 ± 0.028 | 97% | 67% |
| confounded | ofat | 39.53 ± 0.71 | 0.159 ± 0.051 | 93% | 67% |

## Interaction learning

| Policy | Interaction enabled | Mean absolute interaction error |
|---|---:|---:|
| adaptive | 100% | 0.202 |
| random | 100% | 0.264 |
| ofat | 0% | 1.000 |
An omitted interaction counts as zero prediction when measuring error, not as evidence of a zero effect.

± is between-seed standard deviation, not a confidence interval. No policy dominance claim.

Audience grows with time with an oscillating component so it can be distinguished from linear time. The confounded scenario overrides lyrics to match song for every policy, destroying identification. OFAT repeats baseline plus single changes, so it never observes the interaction cell. Interaction selection is attempted every ten runs; each method can fail its exploratory gate. The irrelevant-font scenario deliberately repeats sparse truth to check behavior with a null factor; it does not automatically retire factors. The D scheduler may keep sampling a well-estimated null factor to preserve contrast precision. No bandit baseline is included in v0.1.
