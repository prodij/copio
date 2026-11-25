"""ledger receipts: publish and completion receipts, and which run last saw each record

Session S1 (ledger). The integrator puts this after 0004 in the chain at merge.

- raw_objects.receipt / receipt_sha256: what publishing that raw object did (counts and a digest of the
  records), so a retried publish of the same raw bytes is answered from the receipt instead of repeated.
- sync_runs.receipt / receipt_sha256: what completing the run did (coverage, deletions, raw digests).
  The sha256 columns let a reader verify a receipt was not altered after the fact.
- synced_records.last_seen_run_id: the last run whose pages contained the key, even when its version
  lost. Deletion inference for a complete snapshot tombstones only keys the snapshot run did not see.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "s1_ledger_receipts"
down_revision = "0004"


def upgrade() -> None:
    op.add_column("raw_objects", sa.Column("receipt", pg.JSONB()))
    op.add_column("raw_objects", sa.Column("receipt_sha256", sa.String(64)))
    op.add_column("sync_runs", sa.Column("receipt", pg.JSONB()))
    op.add_column("sync_runs", sa.Column("receipt_sha256", sa.String(64)))
    op.add_column("synced_records",
                  sa.Column("last_seen_run_id", sa.Uuid(), sa.ForeignKey("sync_runs.id", ondelete="SET NULL")))


def downgrade() -> None:
    op.drop_column("synced_records", "last_seen_run_id")
    op.drop_column("sync_runs", "receipt_sha256")
    op.drop_column("sync_runs", "receipt")
    op.drop_column("raw_objects", "receipt_sha256")
    op.drop_column("raw_objects", "receipt")
