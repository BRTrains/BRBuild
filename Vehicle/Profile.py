from dataclasses import dataclass
from typing import Optional, List, Union

@dataclass
class Profile:
    identifier: str
    name: Optional[str] = None
    size: Optional[int] = None
    capacity: Optional[int] = None
    types: Optional[List[str]] = None