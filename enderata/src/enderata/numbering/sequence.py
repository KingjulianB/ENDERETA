"""Persistent postal-ID sequence allocation.

pipeline.py's run_pipeline() defaults to sequencing by sorting
building_id in memory -- deterministic and correct for a fixed, closed
input set (e.g. a test fixture), but wrong for a real, growing
dataset: adding a new building_id can sort before existing ones and
shift their sequence numbers, which violates the "permanent, never
reassigned" postal ID guarantee (see postal_id.py's docstring).

DbSequenceProvider replaces that: once a building_id has been assigned
a sequence number (in the `postal_sequences` table, db/models.py) it
keeps that number forever; a newly-seen building_id gets the next
unused number for its (country_code, district_code) pair. Concurrency
note: the get-or-assign check-then-insert below is safe for the
single-writer batch-job usage this project has today (a numbering run
is not invoked concurrently with itself), not for arbitrary concurrent
writers -- a real multi-writer deployment would need row locking
(e.g. `SELECT ... FOR UPDATE` on Postgres) around the allocation,
intentionally not added here since it's unused for now.
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy import func
from sqlalchemy.orm import Session

from enderata.db.models import PostalSequence


class SequenceProvider(Protocol):
    def next_sequence(self, building_id: str) -> int: ...


class InMemorySequenceProvider:
    """Sequences by sorted building_id within a single run -- the
    previous, still-default behaviour of run_pipeline(). Only valid
    for a fixed, closed input set (see module docstring); kept as the
    default so existing tests/fixtures need no DB and behave exactly
    as before."""

    def __init__(self, building_ids: list[str]):
        self._sequence_for = {
            building_id: sequence for sequence, building_id in enumerate(sorted(building_ids), start=1)
        }

    def next_sequence(self, building_id: str) -> int:
        return self._sequence_for[building_id]


class DbSequenceProvider:
    """Backed by the `postal_sequences` table -- IDs persist across
    separate run_pipeline() calls, so re-running against a growing
    dataset never reassigns an address already issued."""

    def __init__(self, session: Session, country_code: str, district_code: str):
        self._session = session
        self._country_code = country_code.upper()
        self._district_code = district_code.upper()

    def next_sequence(self, building_id: str) -> int:
        existing = self._session.get(PostalSequence, building_id)
        if existing is not None:
            if existing.country_code != self._country_code or existing.district_code != self._district_code:
                raise ValueError(
                    f"building_id {building_id!r} already has a sequence under "
                    f"{existing.country_code}/{existing.district_code}, not "
                    f"{self._country_code}/{self._district_code} -- a building_id must not "
                    "be reused across districts"
                )
            return existing.sequence_number

        max_sequence = (
            self._session.query(func.max(PostalSequence.sequence_number))
            .filter_by(country_code=self._country_code, district_code=self._district_code)
            .scalar()
        )
        next_sequence = (max_sequence or 0) + 1
        self._session.add(
            PostalSequence(
                building_id=building_id,
                country_code=self._country_code,
                district_code=self._district_code,
                sequence_number=next_sequence,
            )
        )
        self._session.flush()
        return next_sequence
