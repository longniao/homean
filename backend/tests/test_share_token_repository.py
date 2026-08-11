from sqlalchemy.dialects.postgresql import dialect

from app.models import Report, ReportShareLink
from app.repositories.delivery import (
    DeliveryRepository,
    legacy_share_token_lookup_hash,
    share_token_lookup_hash,
    share_token_lookup_hashes,
)


class _Result:
    def __init__(self, candidate=None) -> None:  # type: ignore[no-untyped-def]
        self.candidate = candidate

    def tuples(self) -> "_Result":
        return self

    def first(self):  # type: ignore[no-untyped-def]
        return self.candidate


class _Session:
    statement = None

    def __init__(self, candidate=None) -> None:  # type: ignore[no-untyped-def]
        self.candidate = candidate

    async def execute(self, statement) -> _Result:  # type: ignore[no-untyped-def]
        self.statement = statement
        return _Result(self.candidate)


async def test_public_share_lookup_uses_hashed_index_and_one_candidate() -> None:
    session = _Session()
    assert await DeliveryRepository(session).get_public_link("safe-token") is None
    assert session.statement is not None
    compiled = str(session.statement.compile(dialect=dialect()))
    assert "token_lookup_hash" in compiled
    assert " LIMIT " in compiled
    assert "WHERE report_share_links.token =" not in compiled


def test_new_share_hash_is_homean_but_legacy_hash_remains_accepted() -> None:
    token = "safe-token"
    current = share_token_lookup_hash(token)
    legacy = legacy_share_token_lookup_hash(token)

    assert current != legacy
    assert current in share_token_lookup_hashes(token)
    assert legacy in share_token_lookup_hashes(token)


async def test_public_share_lookup_accepts_a_legacy_stored_hash() -> None:
    token = "legacy-token"
    link = ReportShareLink(token=token)
    link.token_lookup_hash = legacy_share_token_lookup_hash(token)
    report = Report()
    session = _Session((link, report))

    assert await DeliveryRepository(session).get_public_link(token) == (link, report)
