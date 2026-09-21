"""GRF data structures public API

Keep this module lightweight — only export small dataclasses and enums.
"""

from .Grf import Grf
from .RailTypeTable import RailTypeTable

__all__ = ["Grf", "RailTypeTable"]
