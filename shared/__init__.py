"""Keryx shared contract.

The frozen interface between CC-A (rail) and CC-B (agent/verifier). Changes here
are coordinated across both instances, never unilateral. See docs/phases.md Phase 0.
"""

from __future__ import annotations

from shared.config import Settings, settings
from shared.rail import MockRail, Rail
from shared.types import (
    Attestation,
    CitationIntent,
    CitationRecord,
    Receipt,
    SettlementStatus,
)

__all__ = [
    "Attestation",
    "CitationIntent",
    "CitationRecord",
    "MockRail",
    "Rail",
    "Receipt",
    "Settings",
    "SettlementStatus",
    "settings",
]
