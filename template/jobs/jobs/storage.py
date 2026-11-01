from datetime import date
from typing import Any


class RawStore:
    """Raw first: every fetched response is kept at a stable key before anything parses it."""

    def __init__(self, bucket: str, client: Any) -> None:
        self.bucket = bucket
        self.client = client

    def put_raw(self, source: str, workspace_id: str, run_id: str, ext: str, body: bytes, when: date) -> str:
        key = f"raw/{source}/{workspace_id}/{when:%Y/%m/%d}/{run_id}.{ext}"
        self.client.put_object(Bucket=self.bucket, Key=key, Body=body)
        return key

    def get(self, key: str) -> bytes:
        body: bytes = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        return body
