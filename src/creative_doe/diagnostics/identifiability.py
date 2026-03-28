"""Likelihood identification independently of priors; detect general linear aliases."""

import numpy as np


def diagnose(x, names, weights=None):
    p = len(names)
    weighted = x if weights is None else x * np.sqrt(weights)[:, None]
    _, singular, vh = np.linalg.svd(weighted, full_matrices=len(weighted) < p)
    tolerance = (
        max(weighted.shape, default=1) * np.finfo(float).eps * (singular[0] if len(singular) else 1)
    )
    rank = int(np.sum(singular > tolerance))
    null = vh[rank:]
    identifiable = np.sum(null**2, axis=0) < 1e-10
    aliases = []
    for vector in null[:12]:
        scale = np.max(np.abs(vector))
        aliases.append(
            {
                name: round(float(v / scale), 4)
                for name, v in zip(names, vector)
                if abs(v / scale) > 0.05
            }
        )
    condition = float(singular[0] / singular[-1]) if rank == p else None
    warnings = []
    if rank < p:
        warnings.append(
            f"Likelihood rank {rank}/{p}: priors stabilize estimates but do not identify aliased effects."
        )
    if condition is not None and condition > 100:
        warnings.append(
            f"Poorly conditioned design ({condition:.0f}); effects may be hard to distinguish."
        )
    if len(x) < 2 * p:
        warnings.append(
            "Few posts relative to model size; intervals are sensitive to assumptions and priors."
        )
    return {
        "rank": rank,
        "columns": p,
        "condition_number": condition,
        "identifiable": dict(zip(names, map(bool, identifiable))),
        "nullspace_relations": aliases,
        "warnings": warnings,
    }
