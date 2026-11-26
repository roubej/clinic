"""Create the keyspace and tables.

Usage (from the project root):
    python -m db.init_schema

Safe to run several times: every statement uses IF NOT EXISTS.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from cassandra.cluster import NoHostAvailable

from .connection import connect

SCHEMA_FILE = Path(__file__).with_name("schema.cql")
MAX_CONNECTION_ATTEMPTS = 120
RETRY_DELAY_SECONDS = 5


def load_statements(path: Path = SCHEMA_FILE) -> list[str]:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"--.*", "", text)  # drop comments
    return [part.strip() for part in text.split(";") if part.strip()]


def main() -> None:
    statements = load_statements()

    cluster = session = None
    for attempt in range(1, MAX_CONNECTION_ATTEMPTS + 1):
        try:
            cluster, session = connect(keyspace=None)
            break
        except NoHostAvailable:
            print(
                f"Cassandra is not ready yet (attempt {attempt}/{MAX_CONNECTION_ATTEMPTS}), "
                f"waiting {RETRY_DELAY_SECONDS} seconds..."
            )
            time.sleep(RETRY_DELAY_SECONDS)
    if session is None:
        sys.exit("Could not reach Cassandra. Is the container running? Try: docker compose ps")

    for statement in statements:
        session.execute(statement)
    print(f"Schema ready ({len(statements)} statements executed).")
    cluster.shutdown()


if __name__ == "__main__":
    main()
