from datetime import date

import boto3
from moto import mock_aws

from jobs.storage import RawStore


@mock_aws
def test_raw_key_layout_and_roundtrip() -> None:
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="raw")
    store = RawStore("raw", client)
    key = store.put_raw("feed", "ws-1", "run-9", "json", b'{"a":1}', date(2026, 10, 31))
    assert key == "raw/feed/ws-1/2026/10/31/run-9.json"
    assert store.get(key) == b'{"a":1}'
