"""Domain model for EventHive."""
from dataclasses import asdict, dataclass

VALID_STATUSES = ["Published","Draft","Cancelled"]
VALID_CATEGORIES = ["Workshop","Talk","Competition","Networking"]
FIELD_NAMES = ["id","title","category","date","capacity","registered_count","status","description","attendees","venue"]

@dataclass
class Event:
    id: int
    title: str
    category: str
    date: str
    capacity: int
    registered_count: int
    status: str
    description: str
    attendees: list[str]
    venue: str

    @property
    def name(self) -> str:
        return str(getattr(self, "title", ""))

    @property
    def searchable_text(self) -> str:
        return " ".join([str(getattr(self, "title", "")), str(getattr(self, "category", "")), str(getattr(self, "venue", "")), str(getattr(self, "description", ""))])

    def to_dict(self) -> dict:
        return asdict(self)

    def validate(self) -> None:
        # Intentionally incomplete for the student evaluation.
        return None

    @classmethod
    def from_dict(cls, row: dict) -> "Event":
        if not isinstance(row, dict):
            raise ValueError("Each record must be a JSON object")
        missing = set(FIELD_NAMES).difference(row)
        if missing:
            raise ValueError("Missing fields: " + ", ".join(sorted(missing)))
        # Domain/cross-record validation is intentionally incomplete.
        return cls(**{key: row[key] for key in FIELD_NAMES})

RECORD_CLASS = Event
