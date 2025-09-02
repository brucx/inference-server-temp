from pathlib import Path

import boto3
import structlog
from minio import Minio

from app.config import settings

logger = structlog.get_logger()


class StorageService:
    def __init__(self):
        self.use_local = settings.use_local_storage

        if not self.use_local:
            self.minio_client = Minio(
                settings.s3_endpoint.replace("http://", "").replace("https://", ""),
                access_key=settings.s3_access_key,
                secret_key=settings.s3_secret_key,
                secure=settings.s3_use_ssl,
            )

            self.s3_client = boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key,
                use_ssl=settings.s3_use_ssl,
            )

            self._ensure_bucket_exists()
        else:
            self.local_path = Path(settings.local_storage_path)
            self.local_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Using local storage at {self.local_path}")

    def _ensure_bucket_exists(self):
        try:
            if not self.minio_client.bucket_exists(settings.s3_bucket):
                self.minio_client.make_bucket(settings.s3_bucket)
                logger.info(f"Created bucket: {settings.s3_bucket}")
        except Exception as e:
            logger.error(f"Failed to ensure bucket exists: {e}")

    def upload_bytes(
        self, data: bytes, key: str, content_type: str = "application/octet-stream"
    ) -> str:
        if self.use_local:
            file_path = self.local_path / key
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "wb") as f:
                f.write(data)

            logger.info(f"Saved file locally: {file_path}")
            return str(file_path)

        else:
            import io

            self.s3_client.put_object(
                Bucket=settings.s3_bucket, Key=key, Body=io.BytesIO(data), ContentType=content_type
            )

            url = f"{settings.s3_endpoint}/{settings.s3_bucket}/{key}"
            logger.info(f"Uploaded to S3: {url}")
            return url

    def download_bytes(self, key: str) -> bytes | None:
        if self.use_local:
            file_path = self.local_path / key

            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return None

            with open(file_path, "rb") as f:
                return f.read()

        else:
            try:
                response = self.s3_client.get_object(Bucket=settings.s3_bucket, Key=key)
                return response["Body"].read()
            except Exception as e:
                logger.error(f"Failed to download from S3: {e}")
                return None

    def delete(self, key: str) -> bool:
        if self.use_local:
            file_path = self.local_path / key

            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted local file: {file_path}")
                return True
            return False

        else:
            try:
                self.s3_client.delete_object(Bucket=settings.s3_bucket, Key=key)
                logger.info(f"Deleted from S3: {key}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete from S3: {e}")
                return False

    def get_url(self, key: str, expires_in: int = 3600) -> str:
        if self.use_local:
            return str(self.local_path / key)

        else:
            return self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.s3_bucket, "Key": key},
                ExpiresIn=expires_in,
            )
