from pathlib import Path

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError


class R2Storage:
    """Cloudflare R2 storage backend, used in production so uploaded files
    survive a Render redeploy (Render's local disk is ephemeral). R2 is
    S3-compatible, so this is a thin wrapper around boto3's S3 client
    pointed at R2's endpoint — same relative_path keys as LocalFileStorage,
    just stored as S3 objects instead of files on disk.
    """

    def __init__(self, *, bucket_name: str, endpoint_url: str, access_key_id: str, secret_access_key: str):
        self.bucket_name = bucket_name
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            # R2 speaks the S3 API but expects path-style addressing and
            # has no real AWS region — "auto" is R2's documented value.
            config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
            region_name="auto",
        )

    def save(self, relative_path: str, content: bytes) -> str:
        self._client.put_object(Bucket=self.bucket_name, Key=relative_path, Body=content)
        return relative_path

    def read_bytes(self, relative_path: str) -> bytes:
        response = self._client.get_object(Bucket=self.bucket_name, Key=relative_path)
        return response["Body"].read()

    def delete(self, relative_path: str) -> None:
        # Best-effort, matching LocalFileStorage: a document's DB row
        # should not become undeletable just because its object was
        # already missing in the bucket.
        try:
            self._client.delete_object(Bucket=self.bucket_name, Key=relative_path)
        except ClientError:
            pass

    def path(self, relative_path: str) -> Path:
        raise NotImplementedError(
            "R2Storage has no local filesystem path — use serving_url() to serve files."
        )

    def exists(self, relative_path: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket_name, Key=relative_path)
            return True
        except ClientError:
            return False

    def serving_url(
        self, relative_path: str, *, filename: str, content_type: str, disposition: str
    ) -> str | None:
        # A short-lived presigned GET URL. R2/S3 lets the presigned URL
        # override the response's Content-Type and Content-Disposition, so
        # PDFs/images/text still open inline and DOCX still downloads with
        # the original filename — same behavior as the local backend,
        # just served directly by R2 instead of proxied through the API.
        return self._client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket_name,
                "Key": relative_path,
                "ResponseContentType": content_type,
                "ResponseContentDisposition": f'{disposition}; filename="{filename}"',
            },
            ExpiresIn=300,
        )
