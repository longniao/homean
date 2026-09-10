from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.storage.s3 import S3Client


@pytest.mark.asyncio
async def test_private_operations_and_public_signatures_use_separate_endpoints():
    settings = Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        redis_url="redis://localhost/0",
        s3_endpoint_url="https://media.example.com",
        s3_internal_endpoint_url="http://127.0.0.1:9010",
        s3_access_key="test",
        s3_secret_key="test-secret",
        s3_bucket="private-media",
        jwt_secret="test-secret",
    )
    private, public = MagicMock(), MagicMock()
    public.generate_presigned_url.return_value = "signed-public-url"
    with patch("app.storage.s3.boto3.client", side_effect=[private, public]) as factory:
        storage = S3Client(settings)
        await storage.check_ready()
        assert await storage.presign_put("key", "audio/mp4", 60) == "signed-public-url"
        assert await storage.presign_get("key", 60) == "signed-public-url"
        await storage.delete_object("key")
    assert factory.call_args_list[0].kwargs["endpoint_url"] == "http://127.0.0.1:9010"
    assert factory.call_args_list[1].kwargs["endpoint_url"] == "https://media.example.com"
    private.head_bucket.assert_called_once_with(Bucket="private-media")
    private.delete_object.assert_called_once_with(Bucket="private-media", Key="key")
    private.generate_presigned_url.assert_not_called()
    assert public.generate_presigned_url.call_count == 2
