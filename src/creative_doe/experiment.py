"""Public workflow and JSON persistence for evolving experiments."""

import csv
import io
import json
import re
from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path

from creative_doe.design.matrix import Encoder
from creative_doe.factors import Context, Factor, Status, validate_levels
from creative_doe.models.gaussian import GaussianShrinkage
from creative_doe.observations import Metric, Observation


def now():
    return datetime.now(UTC).isoformat()


def valid_id(value):
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", value):
        raise ValueError("IDs must start with a letter and contain letters, digits, or underscores")


