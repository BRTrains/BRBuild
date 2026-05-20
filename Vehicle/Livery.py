from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Livery:
    name: str
    sprite_override: Optional[List[int]] = None
    profiles: Optional[List[str]] = None