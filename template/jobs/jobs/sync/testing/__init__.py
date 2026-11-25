"""Synthetic providers for the connector layer's contract suite and local demos.

Synthetic only: no real provider accounts, credentials, data or network calls. Every fault is
deterministic, so a scenario that fails once fails every time.
"""

from jobs.sync.testing.faults import Fault, FaultPlan, FaultRule, SchemaChanged
from jobs.sync.testing.feed import SyntheticFeed
from jobs.sync.testing.report import SyntheticReportProvider
from jobs.sync.testing.world import (
    SYNTHETIC_WORKSPACES,
    SyntheticAccount,
    SyntheticWorld,
)

__all__ = [
    "SYNTHETIC_WORKSPACES",
    "Fault",
    "FaultPlan",
    "FaultRule",
    "SchemaChanged",
    "SyntheticAccount",
    "SyntheticFeed",
    "SyntheticReportProvider",
    "SyntheticWorld",
]
