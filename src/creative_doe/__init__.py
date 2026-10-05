"""Continuous experimental design for creative work."""

from creative_doe.experiment import Experiment
from creative_doe.factors import Status
from creative_doe.observations import Metric

__all__ = ["Experiment", "Metric", "Status"]
__version__ = "0.1.0"
