"""Consistent backup and integrity checks for Athena's private SQLite store.

Backup uses SQLite's online backup API, so no copying an active database file.
Restore is intentionally offline-only and refuses to overwrite existing data.
"""
from __future__ import annotations
import argparse
import datetime as dt
import sqlite3
from pathlib import Path
from core.data.paper_journal import database_path


def integrity_check(path: Path) -> bool:
    if not path.is_file():
        raise FileNotFoundError(path)
    with sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True) as connection:
        result = connection.execute("PRAGMA integrity_check").fetchone()
        return result is not None and result[0] == "ok"


def backup(source: Path | None = None, destination: Path | None = None) -> Path:
    src = Path(source) if source is not None else database_path()
    if not src.is_file():
        raise FileNotFoundError(f"No Athena database at {src}")
    if not integrity_check(src):
        raise ValueError("Source SQLite integrity check failed")
    target = Path(destination) if destination is not None else (
        src.parent / "backups" / f"athena-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%SZ}.sqlite3"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError(f"Backup destination already exists: {target}")
    # Use exclusive creation to avoid overwriting an earlier backup.
    target.touch(exist_ok=False)
    try:
        with sqlite3.connect(src) as live, sqlite3.connect(target) as output:
            live.backup(output)
        if not integrity_check(target):
            raise ValueError("Backup integrity check failed")
        return target
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def restore(backup_file: Path, destination: Path | None = None) -> Path:
    src = Path(backup_file)
    dest = Path(destination) if destination is not None else database_path()
    if not integrity_check(src):
        raise ValueError("Backup integrity check failed")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise FileExistsError("Destination database already exists; restore must not overwrite it")
    # Never restore over the currently running terminal's database.
    dest.touch(exist_ok=False)
    try:
        with sqlite3.connect(src) as source, sqlite3.connect(dest) as output:
            source.backup(output)
        if not integrity_check(dest):
            raise ValueError("Restored database failed integrity check")
        return dest
    except BaseException:
        dest.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline Athena SQLite database management")
    parser.add_argument("action", choices=["backup", "check", "restore"])
    parser.add_argument("--source", type=Path, help="Source database or backup file")
    parser.add_argument("--destination", type=Path, help="New output file; existing files never overwritten")
    args = parser.parse_args()
    if args.action == "check":
        print("SQLite integrity:", "OK" if integrity_check(args.source or database_path()) else "FAILED")
    elif args.action == "backup":
        print("Backup created:", backup(args.source, args.destination))
    else:
        if args.source is None:
            parser.error("restore requires --source (existing backup)")
        print("Restored to:", restore(args.source, args.destination))


if __name__ == "__main__":
    main()
