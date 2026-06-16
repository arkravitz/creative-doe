# Statistical foundations and v0.1 decisions

This is a sequential, model-based design-of-experiments engine for expensive posts. The experimental unit is a **post**, not an impression. Its goal is interpretable learning under a changing creative schema. The literature review below informed the implementation before the statistical core was written. Decisions and derivations labeled as such are this project's choices, not claims that a cited paper validates social-media inference.

## Which research ideas belong here?

| Research branch | Relevant lesson | v0.1 decision |
|---|---|---|
| Full factorial designs | Cross factors to distinguish their contributions. | Enumerate a finite feasible configuration space; do not treat whole posts as unrelated arms. |
| Fractional factorial designs, resolution, aliasing | Fewer runs trade information for assumptions about omitted effects. | Use numerical design diagnostics; do not claim a formal resolution for an arbitrary adaptive design. |
| Sequential design and factor screening | Learn cheaply first, then augment where ambiguity matters. | Refit and select a small next batch; keep the factor lifecycle explicit. |
| Supersaturated designs | More effects than independent runs requires structural assumptions. | Permit exploration but flag rank deficiency; shrinkage is not identification. |
| Effect sparsity, hierarchy, heredity | Most effects may be small; lower-order explanations are preferable starting points. | Gaussian shrinkage, stronger interaction shrinkage, opt-in pairwise interactions with an exploratory evidence gate. |
| Response surface methodology | Quantitative optimization needs curvature and interior points. | Finite candidate domains initially; no automatic quadratic response surface or continuous optimum claim. |
| D-optimality and Bayesian design | Select configurations useful for a specified model. | Greedy conditional Gaussian information gain with a proper prior. |
| A-, G-, and prediction-optimal criteria | Learning all coefficients and predicting well are different objectives. | Document as alternatives; the implemented learning objective is determinant-based. |
| Bayesian variable selection | Sparse priors can separate tiny and large effects. | Defer spike-and-slab/horseshoe inference; ridge is transparent and inexpensive but not sparse selection. |
| Contextual bandits and Thompson sampling | Share information across configurations and account for context. | Useful comparators; reward regret is not the primary estimand. |
| Nonstationary bandits and adaptive experimentation | Old observations can become less relevant. | Optional recency weighting, explicitly a discounted working model. |
| Information gain and model discrimination | Learning parameter values differs from choosing between models. | Compute conditional coefficient information, not model-entropy reduction. |
| Blocking, covariate adjustment, hierarchical models | Song/platform/time context can overwhelm creative effects. | Model observed context separately; compare within blocks where possible. Learned multilevel variance components are future work. |

## Factorial thinking with a changing design

Crossing two binary factors produces four cells. Repeating one factor at only one level of the other cannot generally distinguish both main effects and their interaction. Regular two-level fractions have precise alias structures: resolution III can alias main effects with two-factor interactions; resolution IV separates those but may alias two-factor interactions with one another; resolution V separates main effects and two-factor interactions from each other, while higher-order aliases remain. These guarantees rely on that particular regular design, not merely on collecting a fraction of all combinations. See [NIST's resolution definitions](https://www.itl.nist.gov/div898/handbook/pri/section3/pri3324.htm).

A creator rarely runs a textbook fraction unchanged: forbidden combinations, batches of three, new factors, and changing songs destroy its simple structure. The useful principle is to inspect the actual model matrix and add configurations that distinguish its columns. Follow-up augmentation can break aliases; a classical example is [foldover design](https://www.itl.nist.gov/div898/handbook/pri/section3/pri3381.htm). This package uses greedy numerical augmentation rather than claiming to implement a catalog of foldovers.

Screening asks which factors deserve scarce follow-up resources. Supersaturated designs have more candidate main-effect parameters than the data can jointly estimate without assumptions; sparsity can help, but correlated effects can still be misattributed. Sequential group screening and bifurcation also require assumptions that are unattractive for highly noisy posts with opposing effects. [Woods and Lewis's screening review](https://arxiv.org/abs/1510.05248) compares these approaches. v0.1 keeps a small interpretable model and makes insufficient evidence visible.

Response surface methods support sequential movement from screening toward local quantitative optimization; categorical fonts and hooks have no meaningful derivative or quadratic distance. A future duration/size optimizer would need explicit numeric scaling, center/interior points, and curvature checks. See [NIST's response-surface design material](https://www.itl.nist.gov/div898/handbook/pri/section3/pri336.htm).

## The working regression model

For post-level transformed outcomes, use the conjugate model

```text
y_i | beta, sigma² ~ Normal(x_i beta, sigma²)
beta | sigma²     ~ Normal(m0, sigma² Lambda0^-1)
sigma²            ~ InverseGamma(a0, b0)
```

`x_i` includes an intercept, encoded creative contrasts, optional pairwise products, context/blocking terms, and a linear trend `(run - 1)/30`. Run is ingestion order, not elapsed calendar time. Users must enter observations in publication order; delayed-outcome reordering is deferred. The prior precision `Lambda0` must be positive definite. Defaults: zero coefficient means, `a0=2`, `b0=1`, and conditional coefficient standard-deviation multipliers (relative to residual sigma) of 10 for the intercept, 1.5 for main effects, 0.75 for interactions, and 2 for context/time. These are transparent fixed priors, not empirically estimated sparsity. Early recovery checks revealed excessive interaction attenuation with a 0.35 multiplier, so the default was widened; this simulator-informed tuning means the reported benchmark is development validation, not a held-out comparison. Perform prior sensitivity checks for real work. Main effects shrink toward zero; interactions receive stronger shrinkage. This is Gaussian ridge regularization, **not** a spike-and-slab posterior, a learned horseshoe, or an estimate of the number of truly nonzero effects. Conjugate Gaussian analysis is a standard foundation; see [Murphy's technical note](https://www.cs.ubc.ca/~murphyk/Papers/bayesGauss.pdf).

The following weighted formulas are the project's direct conjugate derivation. With diagonal nonnegative `W`, they follow by completing the square in the product of likelihoods raised to weights:

```text
Lambda_n = Lambda0 + X' W X
m_n      = Lambda_n^-1 (Lambda0 m0 + X' W y)
a_n      = a0 + sum(w_i)/2
b_n      = b0 + (y' W y + m0' Lambda0 m0 - m_n' Lambda_n m_n)/2
beta | D ~ multivariate Student-t(2 a_n, m_n, (b_n/a_n) Lambda_n^-1)
```

The Student-t matrix above is a **scale matrix**, not its covariance. When `a_n > 1`, covariance is `b_n/(a_n-1) * Lambda_n^-1`. The predictive scale also includes observation noise. Marginal coefficient intervals are conditional on the chosen schema, coding, priors, transformations, and likelihood; they do not include model-selection uncertainty.

For a categorical factor, a reported coefficient is a contrast to the encoder's reference level. In a model with interactions it is conditional on other interacting factors being at their reference levels. It is not automatically an average marginal causal effect. Numeric factor grids use the same categorical reference contrasts in v0.1; numeric context variables instead use declared centering and scaling. Compare like contrasts when evaluating recovery.

Continuous outcomes are modeled on their stated scale; nonnegative counts use `log(1 + count)`. Proportions preserve numerator and denominator and use `log((numerator + 0.5)/(denominator - numerator + 0.5))` for this working regression. The denominator is not treated as thousands of independent experimental replications. A transformed post-level model is an approximation: it avoids false binomial precision but does not solve heteroskedasticity or zero inflation. Never mix different outcomes into an undeclared score.

Gaussian shrinkage stabilizes the fit with few posts but shrinks large effects as well as small ones and is sensitive to scale. A [regularized horseshoe](https://www.projecteuclid.org/journals/electronic-journal-of-statistics/volume-11/issue-2/Sparsity-information-and-regularization-in-the-horseshoe-and-other-shrinkage/10.1214/17-EJS1337SI.pdf) is a defensible later option when sparsity-specific inference justifies its computational and diagnostic burden. v0.1 does not advertise ridge as implementing that method.

## What the scheduler actually learns

Classical D-optimal design maximizes `det(X'X)` for a specified model; constraints motivate selection from a feasible candidate set. The result need not be orthogonal or globally optimal. [NIST's D-optimal design reference](https://www.itl.nist.gov/div898/handbook/pri/section5/pri521.htm) explicitly emphasizes these limitations. Other criteria target average coefficient variance or worst/average prediction variance; see [NIST's comparison](https://www.itl.nist.gov/div898/handbook/pmd/section3/pmd34.htm).

Bayesian experimental design chooses experiments through posterior expected utility; information is one possible utility, not a synonym for any uncertainty heuristic. See [Chaloner and Verdinelli (1995)](https://www.stat.cmu.edu/tr/tr599/tr599.html).

For the conjugate model above, let `A = Lambda_n^-1`. For a prospective unweighted row `x`, the exact expected information about coefficients **conditional on the residual variance** is

```text
I(beta; y_new | D, x, sigma²) = 0.5 log(1 + x' A x).
```

This follows directly from Gaussian entropy and the determinant lemma: `det(Lambda_n + xx') / det(Lambda_n) = 1 + x'Ax`. Because the conditional expression does not depend on `sigma²`, averaging it over the current variance posterior leaves it unchanged. It is not the full joint information about `(beta, sigma²)`, nor generally the marginal information about `beta` after integrating out variance. The documented name is **conditional Gaussian information gain**, in nats.

Within a batch, update `Lambda <- Lambda + xx'` after each chosen row. No fictional observed outcome is required for this covariance update. The scoring model assumes future rows have unit weight and the current local regression continues to apply. Planning against a fixed discounted posterior is not an exact forecast of future drift.

The scheduler combines separately min–max normalized learning and predicted transformed performance scores with the requested exploration weight. Balance is a hard within-batch constraint, not a soft information bonus. Equal scores are broken by a seeded random tie-breaker. The policy does not log assignment probabilities or guarantee randomized treatment overlap. The mixture is an engineering utility with a user-selected tradeoff, not itself mutual information or a proven optimal policy. Constraints can make a balanced or identified design impossible; return warnings rather than inventing certainty. Information about nuisance coefficients also enters a full determinant criterion; targeted creative-contrast information is a future refinement.

Model discrimination instead asks which rival mechanisms explain the data. It requires explicit rival models and predictive distributions; coefficient variance reduction within one model is insufficient. [Box and Hill (1967)](https://www.tandfonline.com/doi/abs/10.1080/00401706.1967.10490441) is a foundational reference. v0.1 does not implement Bayes factors or posterior model-entropy optimization.

## Identification comes from the likelihood, not the prior

Inspect the unregularized weighted model matrix. Full column rank is necessary for jointly identifying its coefficients under the regression model. Pairwise column correlations alone miss dependencies involving three or more columns. Singular values, rank, and null-space directions expose these problems. A contrast `c'beta` is estimable from the design exactly when `c` is orthogonal to its null space.

For example, if `font_serif == hook_question` for every observed post, only their combined coefficient can be learned. A proper prior produces separate finite posterior numbers, but their separation is prior driven. Neither narrow shrinkage intervals nor a nonsingular posterior precision changes this fact. Numerical near-singularity also matters even when formal rank is full. Diagnostics describe the included model; they cannot establish the absence of omitted-interaction bias or unmeasured confounding.

## Evolving factors and the estimand

These are deliberate storage and analysis choices, not a new missing-data theorem:

1. Stable factor IDs and schema snapshots preserve the definition in force when each observation was recorded.
2. Pre-introduction values stay unknown. An omitted value is not `False`, the reference level, an inactive state, or a zero coefficient.
3. For a selected current regression, only observations whose required predictors and metric are known enter that fit. Report excluded rows. Older observations remain queryable and can support a model restricted to older factors.
4. Adding a factor can therefore reduce the analysis sample for every coefficient in a joint model. Estimates before and after that change target different observed periods/populations. Avoid silently comparing them as the same estimand.
5. Retirement stops deliberate manipulation; retain historical levels and coefficients where the selected analysis can use them. Holding a retired factor constant prospectively does not mean its historical effect disappeared.
6. Reactivation supplies new contrast information. Removed levels remain historical categories; adding a new level supplies a new contrast with little or no data evidence.

This conservative complete-case rule avoids fabricated historical evidence, but it is not generally unbiased under outcome-dependent missingness. New-factor effects cannot be identified from old posts that never measured the factor. More efficient joint models would need justified assumptions about latent historical settings, missingness, eras, and transportability.

## Hierarchy, heredity, and interaction restraint

Effect hierarchy prefers lower-order terms before high-order ones. Strong heredity keeps both parent main effects when including their interaction; weak heredity requires at least one. [Bien, Taylor, and Tibshirani (2013)](https://arxiv.org/abs/1205.5050) formalize hierarchical interaction regularization. These principles are useful structure, not natural laws: a pure crossover interaction can exist with zero marginal main effects.

v0.1 explores pairwise interactions only through explicit opt-in and a gate using parent evidence, adequate data, and design estimability. The gate is a conservative workflow heuristic, **not** that paper's hierarchical lasso, a calibrated significance test, or a false-discovery procedure. Keep parent terms, apply stronger interaction shrinkage, and treat post-selection intervals as exploratory. Validate interesting interactions using fresh crossed configurations. The policy can miss genuine interactions with weak parents; exhaustive combinatorial testing is intentionally excluded.

## Context, blocks, and time

Separate controlled choices from observed context. Song, platform, posting slot, and prior audience state can shift baselines. A prospective block plan should vary creative factors within comparable songs/slots rather than assigning one treatment to one song. [NIST's blocking reference](https://www.itl.nist.gov/div898/handbook/pri/section3/pri332.htm) explains the design principle. Regression adjustment uses measured predictors but cannot compensate for absent overlap or unobserved confounding. [Lin's randomized-experiment analysis](https://escholarship.org/uc/item/2wk083kq) gives a more careful basis for adjustment than assuming regression is automatically causal; its asymptotic guarantees do not transfer wholesale to this adaptive ridge model.

Context indicators with fixed shrinkage are a limited form of regularization. They do not estimate population distributions of song effects or random slopes. Fully multilevel models can pool baselines and heterogeneity across songs, but their causal interpretation still needs assumptions; see [Gelman, “Multilevel (Hierarchical) Modeling: What It Can and Cannot Do”](https://stat.columbia.edu/~gelman/research/published/multi2.pdf).

Optional exponential recency weights use `w_i = 2^(-age_i / half_life)` in a power likelihood. This defines a local, discounted working posterior. [Bissiri, Holmes, and Walker (2016)](https://pmc.ncbi.nlm.nih.gov/articles/PMC5082587/) motivates generalized belief updating through loss; it does **not** validate this particular half-life or interval coverage under drift. Report both actual retained posts and the sum of weights. Neither is automatically the effective independent sample size when posts are dependent.

Recency weighting forgets; it does not forecast change points, identify varying slopes, or correct abrupt platform changes. Time covariates can represent baseline trends, but when a factor changes only with time, its effect remains entangled with the trend. Nonstationary bandit theory explicitly depends on assumptions about reward variation; see [Besbes, Gur, and Zeevi (2014)](https://proceedings.neurips.cc/paper_files/paper/2014/hash/91ba7292e5388b90b58d0b839a7f19ec-Abstract.html). No regret guarantee from that work is claimed here.

## Why this is not simply a bandit

A contextual bandit can share information across actions, so it would be inaccurate to equate every bandit with independent whole-post arms. [Li et al. (2010)](https://arxiv.org/abs/1003.0146) use context for reward-oriented recommendation; [Russo et al.'s Thompson-sampling tutorial](https://arxiv.org/abs/1707.02038) covers structured posterior sampling. Those are useful baselines or future alternative policies.

This engine instead makes factor contrasts, design rank, schema changes, and learning utility explicit. Maximizing cumulative outcomes can concentrate on a few configurations and leave effects unidentifiable. Maximizing determinant gain can spend posts on scientifically useful but mediocre content. Neither dominates universally. Simulation therefore reports both reward and effect-estimation error, with known truth and multiple seeds where practical. Synthetic recovery is a software/model check, not proof of causal validity on a real platform.

## Scientific status

The conjugate update and conditional Gaussian gain are mathematically established within their working model. The interaction evidence gate, utility normalization, greedy feasibility search, complete-case transport interpretation, and chosen drift half-life have **no general calibration or optimality guarantee**. The model's usefulness must be evaluated with sensitivity analysis, real replication, and simulator stress tests. Read [limitations.md](limitations.md) before interpreting any effect as causal.
