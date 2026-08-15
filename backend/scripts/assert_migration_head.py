"""Assert that the checked-in Alembic graph has the expected single head."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

EXPECTED_ALEMBIC_HEAD = "20260814_0022"


def main() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    heads = tuple(script.get_heads())

    if len(heads) != 1:
        raise SystemExit(
            "Alembic migration graph must have exactly one head; "
            f"found {len(heads)}: {', '.join(heads) or '(none)'}"
        )

    if heads[0] != EXPECTED_ALEMBIC_HEAD:
        raise SystemExit(
            "Alembic migration graph has an unexpected head: "
            f"expected {EXPECTED_ALEMBIC_HEAD}, found {heads[0]}"
        )

    if script.get_revision(EXPECTED_ALEMBIC_HEAD) is None:
        raise SystemExit(
            f"Expected Alembic head {EXPECTED_ALEMBIC_HEAD} is not present"
        )

    print(f"Alembic migration graph: one expected head ({heads[0]})")


if __name__ == "__main__":
    main()
