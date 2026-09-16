from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Livery:
    name: str
    size: Optional[int] = None
    sprite_override: Optional[List[int]] = None
    sprite_exclude: Optional[List[int]] = None
    profiles: Optional[List[str]] = None