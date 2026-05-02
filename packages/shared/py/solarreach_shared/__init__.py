"""SolarReach shared package — Pydantic models, financial math, compliance helpers."""

from .financial import composite_score, roi_gate, capex, payback_years, npv_25yr
from .compliance import hash_recipient, is_live_outbound
from . import constants
from . import industry_benchmarks
from . import models

__all__ = [
    "composite_score",
    "roi_gate",
    "capex",
    "payback_years",
    "npv_25yr",
    "hash_recipient",
    "is_live_outbound",
    "constants",
    "industry_benchmarks",
    "models",
]

__version__ = "0.1.0"
