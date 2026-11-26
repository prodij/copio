"""The `implementations` fixture: every contract scenario runs once per implementation.

`memory` needs nothing. `postgres` uses the real schema through `two_workspaces` / `clean_tables` from
jobs/tests/conftest.py (TEST_DATABASE_URL), so it needs a Postgres.
"""

from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws

from .harness import Harness, memory_harness, postgres_harness

IMPLEMENTATIONS = ["memory", "postgres"]
BUCKET = "contract-raw"


@pytest.fixture
def s3_client() -> Iterator[object]:
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


@pytest.fixture(params=IMPLEMENTATIONS)
def implementations(request: pytest.FixtureRequest, s3_client: object) -> Harness:
    if request.param == "memory":
        return memory_harness(s3_client, BUCKET)
    workspaces = request.getfixturevalue("two_workspaces")
    engine = request.getfixturevalue("clean_tables")
    return postgres_harness(engine, workspaces, s3_client, BUCKET)
