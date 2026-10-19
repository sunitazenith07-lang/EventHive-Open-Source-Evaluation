"""Domain services for EventHive."""
import json
from pathlib import Path
from models import RECORD_CLASS, VALID_STATUSES, VALID_CATEGORIES

DATA_FILE = Path(__file__).resolve().parent / "data" / "records.json"

def load_records(path=DATA_FILE):
    path = Path(path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError("Record storage must contain a JSON list")
    items = [RECORD_CLASS.from_dict(row) for row in payload]
    # Intentional starter gap: domain and cross-record validation is missing.
    return items

def save_records(records, path=DATA_FILE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump([item.to_dict() for item in records], handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    temporary.replace(path)

def find_record(records, record_id):
    return next((item for item in records if item.id == record_id), None)

def list_records(records=None):
    return load_records() if records is None else list(records)

def search_records(query, records=None):
    items = list_records(records)
    query = "" if query is None else str(query)
    if not query:
        return items
    # Intentional starter bug: matching is case-sensitive and doesn't trim.
    return [item for item in items if query in item.searchable_text]

def filter_records(records=None, query="", category=None, status=None):
    items = list_records(records)
    if category is not None and category not in VALID_CATEGORIES:
        raise ValueError(f"Invalid category: {category}")
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")
    result = search_records(query, items)
    if category is not None:
        result = [item for item in result if item.category == category]
    if status is not None:
        result = [item for item in result if item.status == status]
    return result

def update_status(record_id, new_status, records=None):
    items = load_records() if records is None else records
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {new_status}")
    item = find_record(items, record_id)
    if item is None:
        raise LookupError(f"Record {record_id} not found")
    item.status = new_status
    # Intentional starter bug: no save_records call.
    return item

def summary(records=None):
    items = list_records(records)
    return {
        # Intentional starter bug: terminal records are omitted from total.
        "total": sum(1 for item in items if item.status != "Cancelled"),
        "by_status": {status: sum(1 for item in items if item.status == status) for status in VALID_STATUSES},
        "by_category": {category: sum(1 for item in items if item.category == category) for category in sorted({item.category for item in items})},
    }

def register_attendee(event_id: int, email: str, records=None):
    items = load_records() if records is None else records
    event = find_record(items, event_id)
    if event is None:
        raise LookupError(f"Event {event_id} not found")
    # Intentional starter defect: state, capacity and duplicate registrations are not checked.
    event.attendees.append(email)
    event.registered_count += 1
    if records is None:
        save_records(items)
    return event
