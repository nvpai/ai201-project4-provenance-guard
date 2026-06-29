"""Structured audit log backed by a JSON file (one decision per entry)."""
import json
import os
from datetime import datetime, timezone

LOG_PATH = os.path.join(os.path.dirname(__file__), "audit_log.json")


def _read():
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH) as f:
        return json.load(f)


def _write(entries):
    with open(LOG_PATH, "w") as f:
        json.dump(entries, f, indent=2)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def add_entry(entry):
    """Append a structured entry and persist it."""
    entries = _read()
    entries.append(entry)
    _write(entries)
    return entry


def get_log(limit=20):
    """Return the most recent entries (newest last)."""
    return _read()[-limit:]


def find_entry(content_id):
    """Return the entry for a content_id, or None."""
    for entry in _read():
        if entry.get("content_id") == content_id:
            return entry
    return None


def update_entry(content_id, updates):
    """Merge updates into the matching entry. Returns the entry or None."""
    entries = _read()
    target = None
    for entry in entries:
        if entry.get("content_id") == content_id:
            entry.update(updates)
            target = entry
    if target is not None:
        _write(entries)
    return target
