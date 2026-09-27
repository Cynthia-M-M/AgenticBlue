"""
Database scanner — walks SQLModel / SQLAlchemy model definitions.
Currently a stub; the demo_project does not use a DB model layer,
but this module is here for future extension.
"""
from __future__ import annotations

from pathlib import Path
from typing import List


def scan_database(directory: Path) -> List[dict]:
    """Return any SQLModel table definitions found under `directory`."""
    # Stub — not needed for MVP demo
    return []
