from sqlalchemy.dialects.postgresql import dialect

from app.repositories.delivery import DeliveryRepository


class _Result:
    def tuples(self) -> "_Result":
        return self

    def first(self) -> None:
        return None


class _Session:
    statement = None

    async def execute(self, statement) -> _Result:  # type: ignore[no-untyped-def]
        self.statement = statement
        return _Result()


async def test_public_share_lookup_uses_hashed_index_and_one_candidate() -> None:
    session = _Session()
    assert await DeliveryRepository(session).get_public_link("safe-token") is None
    assert session.statement is not None
    compiled = str(session.statement.compile(dialect=dialect()))
    assert "token_lookup_hash" in compiled
    assert " LIMIT " in compiled
    assert "WHERE report_share_links.token =" not in compiled
