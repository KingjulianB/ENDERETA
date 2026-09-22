"""Best-effort connection to the real Postgres database (config.py's
DATABASE_URL) for persistent postal-ID sequencing (numbering/sequence.py).

Not exercised against a live Postgres in this dev environment (no
Docker/Postgres available here -- see numbering/sequence.py's tests,
which verify the same SQLAlchemy code against a real SQLite file
instead). In the add-on itself, run.sh already starts a bundled
Postgres before the Flask server/CLI run, so DATABASE_URL should be
reachable there -- but that specific path is unverified until checked
on a real HA run.

If the DB is unreachable for any reason, `open_sequence_provider`
returns (None, None) and callers fall back to run_pipeline()'s default
InMemorySequenceProvider (in-memory, not persistent -- documented
limitation) rather than crashing the whole request.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from enderata.config import load_settings
from enderata.db.models import PostalSequence
from enderata.numbering.sequence import DbSequenceProvider


def open_sequence_provider(
    country_code: str, district_code: str
) -> tuple[DbSequenceProvider | None, Session | None]:
    """Try to open a real, persistent sequence provider. Returns
    (None, None) if the database isn't reachable -- caller should pass
    the provider straight to run_pipeline()'s sequence_provider param,
    commit the session after a successful run, and close it either way."""
    settings = load_settings()
    try:
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        PostalSequence.__table__.create(engine, checkfirst=True)
        session = Session(engine)
    except Exception as exc:  # noqa: BLE001 -- any DB failure should degrade, not crash
        print(f"[db.session] persistent sequencing unavailable ({exc}); falling back to in-memory sequencing")
        return None, None
    return DbSequenceProvider(session, country_code, district_code), session
