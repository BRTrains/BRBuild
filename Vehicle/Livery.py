from dataclasses import dataclass
from typing import Optional, List, Union

@dataclass
class Livery:
    name: str
    sprite_override: Optional[List[int]] = None
    profiles: Optional[List[str]] = None