from urllib.parse import quote

from app.storage.provider import StorageProvider, StoredObject, StoredObjectBody


class FakeStorageProvider(StorageProvider):
    def __init__(self) -> None:
        self.objects: dict[str, StoredObject] = {}
        self.object_bodies: dict[str, StoredObjectBody] = {}
        self.presigned_puts: list[str] = []
        self.presigned_gets: list[str] = []

    async def presign_put(
        self, object_key: str, content_type: str, expires_in: int
    ) -> str:
        del content_type, expires_in
        self.presigned_puts.append(object_key)
        return f"https://storage.test/upload/{quote(object_key)}"

    async def head_object(self, object_key: str) -> StoredObject | None:
        return self.objects.get(object_key)

    async def presign_get(self, object_key: str, expires_in: int) -> str:
        del expires_in
        self.presigned_gets.append(object_key)
        return f"https://storage.test/download/{quote(object_key)}"

    async def get_object_bytes(self, object_key: str) -> StoredObjectBody | None:
        return self.object_bodies.get(object_key)

    def put_object(self, object_key: str, content_type: str, size_bytes: int) -> None:
        self.objects[object_key] = StoredObject(
            size_bytes=size_bytes, content_type=content_type
        )

    def put_object_bytes(
        self, object_key: str, content_type: str, data: bytes
    ) -> None:
        self.put_object(object_key, content_type, len(data))
        self.object_bodies[object_key] = StoredObjectBody(
            data=data, content_type=content_type
        )
