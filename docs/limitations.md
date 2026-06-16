# Limitations and interpretation

This package is a research MVP. An effect estimate is a conditional regression contrast with uncertainty under an assumed model. It is not evidence that a platform would deliver the same causal benefit if every creator adopted a creative choice.

## When causal language is inappropriate

Do not interpret a result causally when creative choices were selected using unrecorded information related to likely performance; a treatment appeared only for a particular song, period, or platform; comparable alternative configurations were infeasible; posts affected one another; outcome collection depended on observed success; or model assumptions were not credible. A full-rank design alone does not rule out these problems.

For a local causal interpretation one would need a well-defined intervention and outcome window, consistency of its implementation, comparable treatment opportunities, assignment independent of potential outcomes conditional on the recorded history, and an adequate account of interference, carryover, and missingness. Randomizing feasible choices within comparable blocks helps. The scheduler's recommendations and deterministic constraints are not equivalent to a randomized controlled trial.

## Social-media interference and distribution

The creator cannot literally randomize the platform's distribution algorithm. Algorithms select viewers and exposure volumes using signals affected by the content, account history, audience state, and concurrent events. A views effect may combine creative response with algorithmic distribution. A hold-rate effect conditions on a selected audience and is not necessarily an effect on a fixed audience.

Posts can compete, prime viewers, change followers, and influence delivery of later posts. A viral post can change the audience for subsequent observations. Repetition causes fatigue or familiarity; song campaigns have carryover. v0.1 has no network-interference model, causal mediation analysis, or identified washout period. Cooldowns are practical constraints rather than a statistical correction for carryover.

## Few posts, many unknowns

Ten posts remain ten experimental units even if they generate a million impressions. Repeated viewers, clustered exposure, overdispersion, and algorithmic feedback make naïve binomial precision inappropriate. Gaussian post-level errors also remain an approximation and can be strongly heteroskedastic or heavy-tailed.

Shrinkage stabilizes estimates but can suppress real effects and create reassuring intervals in directions the data do not identify. Rank and alias warnings take precedence over coefficient rankings. Full rank with only slightly more runs than columns can still mean almost no usable precision. Collect cross-factor overlap and replication before retiring factors on evidence grounds.

Failure to establish a meaningful effect is not evidence of equivalence. Retirement is a reversible workflow decision. If a smallest effect of interest is specified, evidence that the full relevant interval lies inside that region is more informative than an interval merely containing zero; even that judgment is model dependent and vulnerable to drift.

## Schema evolution changes what can be learned

Pre-introduction factor values remain unknown. The current joint fit uses only complete rows for its chosen predictors and metric, so adding a factor can discard most older observations from that particular fit. Stored history is preserved; statistical evidence is not magically transferred into the new factor.

Complete cases can describe a selected era or population. Their results are not automatically comparable with earlier estimates. Missingness related to content quality or outcomes can bias them. Including retired factor terms preserves historical adjustment where data permit, but incomplete retired-factor records can further shrink the current analysis set. Reconstruct historical values only from defensible records and preserve provenance.

Reference coding matters. Adding a level changes available contrasts; removing a level does not erase its old observations. Do not interpret an interaction-conditioned coefficient as an average over all old and new levels.

## Nonstationarity and contextual confounding

Songs, audiences, time of day, seasonality, creator skill, recent viral posts, and platform policy can all change together. Recording context does not make it exogenous. Avoid adjusting for post-treatment variables such as realized impressions when the target is the total effect on reach; such adjustment can change the question or introduce bias.

Recency weighting is a discounted power likelihood, not a generative time-series model. Its half-life is user chosen. It trades bias toward old behavior for higher current variance, can miss abrupt reversals, and does not provide drift-robust coverage. A time trend cannot rescue a factor perfectly aligned with time. Holding the current schema fixed during a batch is a planning approximation.

Fixed-shrinkage song indicators are not a fully learned hierarchical model. There is no posterior over between-song variance, automatic random slopes, or guarantee of transport to a new song. [Gelman's discussion](https://stat.columbia.edu/~gelman/research/published/multi2.pdf) is useful background on both the benefits and causal limits of multilevel modeling.

## Interaction and selection uncertainty

The pairwise strong-heredity gate is an exploratory policy, not a calibrated test. It can miss pure interactions with no main effects. Testing many candidate interactions, reviewing many metrics, adding factors after inspecting winners, and repeatedly checking intervals create selection effects. Stronger shrinkage helps regularization but does not furnish automatic false-discovery control.

Reported intervals condition on the selected model and do not account for its selection. They are not simultaneous confidence statements or guarantees under optional stopping and misspecification. Adaptive assignment can be handled in a correctly specified likelihood conditional on observed history, but that does not make ordinary frequentist coverage or arbitrary post-selection claims valid. Confirm promising interactions and effects with a fresh, deliberately crossed follow-up design.

## Metrics and likelihoods

Choose one primary outcome and a fixed collection horizon before collecting results. Mixing 24-hour views with lifetime views introduces exposure-age bias. Likes, shares, hold rate, and follows answer different questions and must not be pooled into an undeclared engagement score.

The MVP stores numerators and denominators but uses a declared post-level working transformation rather than a fitted beta-binomial or negative-binomial likelihood. Smoothed logits near zero or one depend on the smoothing convention. Unequal denominators imply unequal measurement precision, which a homoskedastic working regression does not fully represent. Log-count predictions transformed back to counts describe a transformed center, not automatically a noise-corrected arithmetic mean. Do not display coefficient precision as a guaranteed percentage-point lift.

Boundary rates, denominator changes, metric-definition changes, delayed outcomes, deleted posts, bots, and measurement errors require inspection. The package does not infer the platform's measurement process. Missing or censored unsuccessful posts are especially problematic.

## Scheduler guarantees are deliberately limited

The learning score is conditional Gaussian coefficient information under the current model. It is not expected reduction in uncertainty over competing models, causal mechanisms, or all future outcomes. The prior contributes information geometry; a new unseen factor is uncertain because of its prior, not because existing data measured it.

Greedy batch selection is not globally D-optimal. Mixing normalized information and predicted performance is a user utility, not an information-theoretic identity or regret guarantee. Hard within-batch balance may conflict with forbidden combinations, fixed blocks, repetition limits, and maximum simultaneous changes. If constraints force confounding, the engine cannot solve that by statistical estimation.

Finite candidate enumeration scales exponentially. The design targets the supplied candidate set, not every imaginable creative choice. A baseline policy's worse performance in a small synthetic benchmark does not establish superiority on a platform.

## What simulation establishes

Known-truth simulation can catch broken encoders, leakage from future factors, biased formulas, failures to learn under overlap, and consequences of drift or confounding. It cannot establish the correctness of the simulator's causal model, platform realism, or uncertainty calibration under arbitrary real-world noise. Compare reward and contrast error separately. Use multiple seeds and inspect failures, including scenarios where random selection outperforms the adaptive policy.

The most consequential next statistical improvements are denominator-aware overdispersed likelihoods; robust and hierarchical post-level models; targeted contrast design with proper block plans; prospective randomized validation with assignment logs; and calibrated sensitivity/coverage studies under drift and adaptive interaction selection. Until those are demonstrated, use this tool to organize experiments and form hypotheses, with explicit uncertainty.

## Data entry and persistence

Run age is based on ingestion order, not timestamps or elapsed days. Enter posts in publication order. There is no pending-post reservation, delayed-outcome join, or deduplication; repeated CSV imports add duplicate evidence. A saved experiment JSON preserves schema definitions; CSV alone does not. Loading untrusted JSON is not a migration/recovery mechanism. Public factor/schema containers are inspectable Python objects; change them through the provided lifecycle methods so the audit trail remains coherent.
