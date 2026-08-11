"""Build and run Playwright while owning its isolated database lifecycle."""

import asyncio
import os
import shutil
import subprocess
import uuid
from pathlib import Path

import asyncpg


async def drop_database(admin_url: str, database_name: str) -> None:
    connection = await asyncpg.connect(
        admin_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        await connection.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = $1 AND pid <> pg_backend_pid()",
            database_name,
        )
        await connection.execute(f'DROP DATABASE IF EXISTS "{database_name}"')
    finally:
        await connection.close()


def main() -> int:
    admin_url = os.environ.get(
        "TEST_DATABASE_ADMIN_URL",
        "postgresql+asyncpg://homean:homean@127.0.0.1:55432/postgres",
    )
    database_name = f"homean_e2e_{uuid.uuid4().hex}"
    environment = {**os.environ, "HOMEAN_E2E_DATABASE": database_name}
    try:
        build = subprocess.run(["npm", "run", "build"], check=False)
        if build.returncode:
            return build.returncode
        standalone = Path(".next/standalone")
        shutil.copytree(".next/static", standalone / ".next/static", dirs_exist_ok=True)
        shutil.copytree("public", standalone / "public", dirs_exist_ok=True)
        return subprocess.run(
            ["npx", "playwright", "test"],
            check=False,
            env=environment,
        ).returncode
    finally:
        asyncio.run(drop_database(admin_url, database_name))


if __name__ == "__main__":
    raise SystemExit(main())
