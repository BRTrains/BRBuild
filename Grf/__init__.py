"""GRF data structures public API

Keep this module lightweight — only export small dataclasses and enums.
"""

from .Grf import DEFAULT_GLOBAL_PROPERTIES, Grf
from .RailTypeTable import RailTypeTable

__all__ = ["DEFAULT_GLOBAL_PROPERTIES", "Grf", "RailTypeTable"]
