"""Create an administrator login.

Run inside the application container:
    docker compose exec app python -m db.create_admin
"""
from __future__ import annotations

import getpass
import sys
import uuid

from .connection import connect
from .repository import ClinicError, ClinicRepository


def main() -> None:
    username = input("Admin username: ").strip()
    password = getpass.getpass("Password (12-128 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        sys.exit("Passwords do not match.")

    cluster, session = connect()
    try:
        ClinicRepository(session).create_account(
            username, password, "admin", uuid.uuid4()
        )
    except ClinicError as exc:
        sys.exit(str(exc))
    finally:
        cluster.shutdown()
    print(f"Administrator account created for {username.strip()}.")


if __name__ == "__main__":
    main()
