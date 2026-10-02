"""Shared JSON persistence helpers for traces and checkpoints."""

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
    """Return the current UTC datetime."""

    return datetime.now(UTC)


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""

    return utc_now().isoformat()


def write_json(path: Path, data: Any) -> Path:
    """Write `data` as indented UTF-8 JSON, creating parent folders."""

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False, default=str)

    return path


def read_json(path: Path) -> Any:
    """Read a UTF-8 JSON file."""

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def prune_oldest(directory: Path, keep: int, protect: tuple[str, ...] = ()) -> int:
    """
    Delete all but the `keep` newest entries (files or folders) in `directory`.

    Entries named in `protect` always count as newest, so an entry that was
    just written survives even when timestamps tie.

    Returns how many entries were removed.
    """

    if not directory.is_dir():
        return 0

    entries = sorted(
        directory.iterdir(),
        key=lambda entry: (entry.name in protect, entry.stat().st_mtime),
        reverse=True,
    )

    removed = 0

    for entry in entries[keep:]:
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()

        removed += 1

    return removed
