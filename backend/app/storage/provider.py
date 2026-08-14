from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class StoredObject:
    size_bytes: int
    content_type: str | None


@dataclass(frozen=True)
class StoredObjectBody:
    data: bytes
    content_type: str | None


class StorageProvider(ABC):
    async def check_ready(self) -> None:
        """Verify the backing bucket is reachable when the provider supports it."""
        return None

    @abstractmethod
    async def presign_put(
        self, object_key: str, content_type: str, expires_in: int
    ) -> str:
        """Return a short-lived URL for a private object upload."""

    @abstractmethod
    async def head_object(self, object_key: str) -> StoredObject | None:
        """Return object metadata, or None when the object does not exist."""

    @abstractmethod
    async def presign_get(self, object_key: str, expires_in: int) -> str:
        """Return a short-lived URL for a private object download."""

    @abstractmethod
    async def get_object_bytes(self, object_key: str) -> StoredObjectBody | None:
        """Read a private object for server-side rendering."""

    @abstractmethod
    async def delete_object(self, object_key: str) -> None:
        """Remove a stored object. Deleting an absent object is not an error."""
