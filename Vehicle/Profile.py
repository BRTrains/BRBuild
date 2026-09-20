from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Profile:
    identifier: str
    name: Optional[str] = None
    size: Optional[int] = None
    num_vehicles: Optional[int] = None
    sprite_override: Optional[List[int]] = None
    sprite_exclude: Optional[List[int]] = None
    capacity: Optional[int] = None
    power: Optional[int] = None
    weight: Optional[float] = None
    types: Optional[List[str]] = None
    special_tags: Optional[List[str]] = None