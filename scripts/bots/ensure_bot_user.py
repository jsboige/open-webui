"""Ensure a bot user exists on the local OWUI instance, idempotently.

Designed to run inside an open-webui container via `docker exec`.
Reads BOT_EMAIL, BOT_PASSWORD, BOT_NAME from env (or args).

Behavior:
- If user with email exists: update password, ensure role='user' and is_active=True.
- If not: create the user with role='user' and is_active=True.

Exit code: 0 on success, 1 on error.
"""

from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import select, update

from open_webui.internal.db import get_async_db_context
from open_webui.models.auths import Auth, Auths
from open_webui.models.users import User, Users
from open_webui.utils.auth import get_password_hash


async def ensure(email: str, password: str, name: str) -> str:
    # get_password_hash is a coroutine upstream (it offloads argon2/bcrypt to a
    # thread pool), so it must be awaited: passing the coroutine straight to the
    # UPDATE makes psycopg fail with "cannot adapt type 'coroutine'".
    hashed = await get_password_hash(password)
    async with get_async_db_context() as db:
        existing = (
            await db.execute(select(User).filter(User.email == email))
        ).scalar_one_or_none()
        if existing:
            await db.execute(
                update(Auth).filter_by(id=existing.id).values(password=hashed, active=True)
            )
            new_role = "user" if existing.role == "pending" else existing.role
            await db.execute(
                update(User).filter_by(id=existing.id).values(role=new_role)
            )
            await db.commit()
            return f"UPDATED id={existing.id} role={new_role}"

    user = await Auths().insert_new_auth(
        email=email, password=hashed, name=name, role="user"
    )
    if user is None:
        raise RuntimeError("insert_new_auth returned None")
    return f"CREATED id={user.id}"


def main():
    email = os.environ.get("BOT_EMAIL", "").strip()
    password = os.environ.get("BOT_PASSWORD", "").strip()
    name = os.environ.get("BOT_NAME", "Channel Bot").strip()
    if not email or not password:
        print("ERROR: BOT_EMAIL and BOT_PASSWORD env vars required", file=sys.stderr)
        sys.exit(1)
    result = asyncio.run(ensure(email, password, name))
    print(result)


if __name__ == "__main__":
    main()
