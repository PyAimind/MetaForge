from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class Message:
    sender: str
    receiver: str
    msg_type: str  # Valid values: "CommandMsg" or "ResultMsg"
    phase: int
    payload: dict

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)