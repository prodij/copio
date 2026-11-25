"""The `implementations` fixture: every contract scenario runs once per implementation.

To add Postgres (integrator, once S1, S2 and S3 are merged): add "postgres" to IMPLEMENTATIONS and build
its Harness in `implementations` from `pg_engine`/`clean_tables`, PgLedger, PgCredentialStore and the
audit table. Nothing in the scenario files changes.
"""

from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws

from .harness import Harness, memory_harness

IMPLEMENTATIONS = ["memory"]
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
    raise NotImplementedError(request.param)  # pragma: no cover
