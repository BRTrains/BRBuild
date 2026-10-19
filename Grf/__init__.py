"""GRF data structures public API

Keep this module lightweight — only export small dataclasses and enums.
"""

from .Grf import COST_SCORE_MAX, DEFAULT_GLOBAL_PROPERTIES, Grf
from .RailTypeTable import RailTypeTable

__all__ = ["COST_SCORE_MAX", "DEFAULT_GLOBAL_PROPERTIES", "Grf", "RailTypeTable"]
