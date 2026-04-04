@dataclass
class BoundingBox:
    """
        A template bounding box definition
        [left_x, upper_y, width, height, offset_x, offset_y, (flags), (filename), (mask)]
    """

    left_x: int
    upper_y: int
    width: int
    height: int
    offset_x: int
    offset_y: int
    flags: List[str] # ["WHITE", "NOANIM"] etc
    filename: Optional[str] = None
    mask: Optional[str] = None