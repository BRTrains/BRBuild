from enum import Enum


class NmlTargetType(Enum):
    SELF = "SELF"
    PARENT = "PARENT"

    def __str__(self):
        return self.value

    @classmethod
    def from_str(cls, value):
        if isinstance(value, cls):
            return value
        if not value:
            return cls.SELF
        val_upper = str(value).strip().upper()
        for member in cls:
            if member.name == val_upper or member.value == val_upper:
                return member
        return cls.SELF