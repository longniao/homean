import asyncio
from typing import Any

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from app.core.config import Settings
from app.storage.provider import StorageProvider, StoredObject, StoredObjectBody


class S3Client(StorageProvider):
    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.s3_bucket
        self._client: BaseClient = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
            region_name=settings.s3_region,
        )

    async def presign_put(
        self, object_key: str, content_type: str, expires_in: int
    ) -> str:
        return await asyncio.to_thread(
            self._client.generate_presigned_url,
            "put_object",
            Params={
                "Bucket": self._bucket,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )

    async def head_object(self, object_key: str) -> StoredObject | None:
        try:
            response: dict[str, Any] = await asyncio.to_thread(
                self._client.head_object,
                Bucket=self._bucket,
                Key=object_key,
            )
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise
        return StoredObject(
            size_bytes=int(response["ContentLength"]),
            content_type=response.get("ContentType"),
        )

    async def presign_get(self, object_key: str, expires_in: int) -> str:
        return await asyncio.to_thread(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": object_key},
            ExpiresIn=expires_in,
        )

    async def get_object_bytes(self, object_key: str) -> StoredObjectBody | None:
        def get_object() -> StoredObjectBody:
            response = self._client.get_object(Bucket=self._bucket, Key=object_key)
            return StoredObjectBody(
                data=response["Body"].read(),
                content_type=response.get("ContentType"),
            )

        try:
            return await asyncio.to_thread(get_object)
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise
