from dataclasses import dataclass, field


@dataclass
class Grf:
    grfid: str
    short_name: str
    name: str
    description: str
    version: str
    compatible_version: str
    params: list = field(default_factory=list)
    global_vehicle_switches: list = field(default_factory=list)
    global_actions: list = field(default_factory=list)