import sqlite3
import os
from enum import Enum

DB_PATH = os.environ.get("DB_PATH", "tasks.db")


class TaskStatus(str, Enum):
    """
    Lifecycle states for a task.

    Stored as TEXT in SQLite so rows are human-readable without a lookup table.
    Using str as a mixin means TaskStatus.PENDING == "pending" and json.dumps()
    serialises it as a plain string with no extra work.

    To add a state: add it here. The validator below stays in sync automatically.
    """
    PENDING = "pending"
    DONE    = "done"

    # Python 3.12 changed str(StrEnum) to return 'ClassName.member' instead of
    # the value. Override __str__ so SQLite and json.dumps always get the raw value.
    def __str__(self) -> str:
        return self.value


_VALID_STATUSES = {s.value for s in TaskStatus}


def validate_status(value: str) -> TaskStatus:
    """
    Coerce a raw string into a TaskStatus, raising ValueError if invalid.
    Call this before any DB write so the enum is always the single source of truth.
    Stays in sync with TaskStatus automatically — no manual CHECK to maintain.
    """
    if value not in _VALID_STATUSES:
        valid = ", ".join(sorted(_VALID_STATUSES))
        raise ValueError(f"Invalid status '{value}'. Must be one of: {valid}")
    return TaskStatus(value)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS tasks (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                title   TEXT NOT NULL,
                status  TEXT NOT NULL DEFAULT '{TaskStatus.PENDING}',
                created TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.commit()


def reset_db():
    """Delete all rows from the tasks table and reset the autoincrement counter.

    Called by the eval harness before each prompt run so task state
    from one run cannot bleed into the next.  Resetting sqlite_sequence ensures
    task IDs restart from 1 each run — otherwise delete/complete commands that
    reference specific IDs would behave differently across prompt runs.
    """
    with get_connection() as conn:
        conn.execute("DELETE FROM tasks")
        # Reset autoincrement so IDs are consistent across runs.
        conn.execute("DELETE FROM sqlite_sequence WHERE name='tasks'")
        conn.commit()


if __name__ == "__main__":
    init_db()
    print(f"Database initialised at {DB_PATH}")
