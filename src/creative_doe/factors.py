"""Versioned finite factor domains. Numeric domains are explicit discrete grids in v0.1."""

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Status(str, Enum):
    PROPOSED = "PROPOSED"
    SCREENING = "SCREENING"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"


def validate_levels(levels: list[Any], dtype: str) -> None:
    if dtype not in {"categorical", "boolean", "numeric"}:
        raise ValueError("dtype must be categorical, boolean, or numeric")
    if len(levels) < 2:
        raise ValueError("Provide at least two distinct levels")
    for level in levels:
        if level is None or not isinstance(level, (str, bool, int, float)):
            raise ValueError("Levels must be non-null JSON scalars")
        if isinstance(level, float) and not math.isfinite(level):
            raise ValueError("Levels must be finite")
        if dtype == "boolean" and type(level) is not bool:
            raise ValueError("Boolean levels must be true/false")
        if dtype == "numeric" and (isinstance(level, bool) or not isinstance(level, (int, float))):
            raise ValueError("Numeric levels must be numbers")
    if len(set(levels)) != len(levels):
        raise ValueError("Duplicate or ambiguous levels")


@dataclass
class Factor:
    id: str
    name: str
    levels: list[Any]
    dtype: str = "categorical"
    status: Status = Status.SCREENING
    introduced_run: int = 1
    retired_run: int | None = None
    rationale: str = ""
    sesoi: float | None = None
    fixed_value: Any = None
    events: list[dict] = field(default_factory=list)

    def __post_init__(self):
        validate_levels(self.levels, self.dtype)
        self.status = Status(self.status)
        if self.sesoi is not None and (not math.isfinite(self.sesoi) or self.sesoi <= 0):
            raise ValueError("SESOI must be positive and finite, on the modeled outcome scale")


@dataclass
class Context:
    id: str
    kind: str = "categorical"
    levels: list[Any] = field(default_factory=list)
    center: float = 0.0
    scale: float = 1.0

    def __post_init__(self):
        if self.kind not in {"categorical", "numeric"}:
            raise ValueError("Context kind must be categorical or numeric")
        if self.kind == "categorical":
            validate_levels(self.levels, "categorical")
        if not math.isfinite(self.center) or not math.isfinite(self.scale) or self.scale <= 0:
            raise ValueError("Context scale must be positive and finite")

    def validate(self, value):
        if self.kind == "categorical" and value not in self.levels:
            raise ValueError(f"Unknown context level for {self.id}: {value}")
        if self.kind == "numeric" and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError(f"Context {self.id} must be finite numeric")
