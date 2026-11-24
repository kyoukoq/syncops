"""Create a consistent SQLite snapshot without replacing any existing file."""

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path


def snapshot(source: Path, destination: Path) -> None:
    source = source.resolve(strict=True)
    destination = destination.absolute()
    if not source.is_file():
        raise ValueError("Source must be an existing database file")
    source_uri = f"{source.as_uri()}?mode=ro"
    with closing(sqlite3.connect(source_uri, uri=True)) as source_db:
        with destination.open("xb"):
            pass
        try:
            with closing(sqlite3.connect(destination)) as destination_db:
                source_db.backup(destination_db)
                if destination_db.execute("PRAGMA quick_check").fetchone() != ("ok",):
                    raise RuntimeError("SQLite reported an integrity error in the snapshot")
        except Exception:
            destination.unlink(missing_ok=True)
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Existing SQLite database or backup")
    parser.add_argument("destination", type=Path, help="New path for the consistent copy")
    args = parser.parse_args()
    try:
        snapshot(args.source, args.destination)
    except (OSError, ValueError, sqlite3.Error, RuntimeError) as error:
        parser.exit(1, f"Snapshot failed: {error}\n")
    print("SQLite snapshot created and verified.")


if __name__ == "__main__":
    main()
