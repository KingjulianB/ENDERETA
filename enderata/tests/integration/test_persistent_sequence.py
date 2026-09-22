"""Proves the actual bug numbering/sequence.py's DbSequenceProvider
fixes: pipeline.py's default (InMemorySequenceProvider) reassigns
existing postal IDs when a new building_id sorts before existing ones;
DbSequenceProvider, backed by a real database (SQLite here -- no
PostGIS-specific column is involved, see db/models.py's
PostalSequence), does not.

Uses a real on-disk SQLite file per test (not a mock), exercising
actual SQL persistence across two separate run_pipeline() calls -- the
same real database, but no live Postgres/Docker needed locally; the
production target is Postgres (config.py's DATABASE_URL), and
SQLAlchemy's ORM layer used here is dialect-agnostic.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from enderata.db.models import PostalSequence
from enderata.numbering.sequence import DbSequenceProvider
from enderata.pipeline import run_pipeline

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "synthetic_sample"


def _load_fixture():
    buildings = gpd.read_file(FIXTURE_DIR / "buildings.geojson")
    streets = gpd.read_file(FIXTURE_DIR / "streets.geojson")
    return buildings, streets


def _add_building(buildings_gdf, building_id, lon, lat):
    extra = gpd.GeoDataFrame(
        {"building_id": [building_id]},
        geometry=gpd.points_from_xy([lon], [lat]),
        crs=buildings_gdf.crs,
    )
    return gpd.pd.concat([buildings_gdf, extra], ignore_index=True)


def test_in_memory_provider_reassigns_ids_when_a_new_building_sorts_first():
    """Documents the known, still-default limitation (see pipeline.py's
    docstring): this is the bug DbSequenceProvider exists to fix."""
    buildings, streets = _load_fixture()
    first_run = {item.building_id: item.postal_id for item in run_pipeline(buildings, streets, "AO", "HUA")}

    grown = _add_building(buildings, "b0", 15.737, -12.7751)  # "b0" sorts before "b1"
    second_run = {item.building_id: item.postal_id for item in run_pipeline(grown, streets, "AO", "HUA")}

    shifted = {bid for bid in first_run if second_run.get(bid) != first_run[bid]}
    assert shifted, "expected the in-memory provider to reassign at least one existing ID"


def test_db_sequence_provider_never_reassigns_existing_ids(tmp_path):
    db_path = tmp_path / "sequence_test.sqlite"
    engine = create_engine(f"sqlite:///{db_path}")
    PostalSequence.__table__.create(engine)

    buildings, streets = _load_fixture()
    grown = _add_building(buildings, "b0", 15.737, -12.7751)

    with Session(engine) as session:
        provider = DbSequenceProvider(session, "AO", "HUA")
        first_run = {
            item.building_id: item.postal_id
            for item in run_pipeline(buildings, streets, "AO", "HUA", sequence_provider=provider)
        }
        session.commit()

    with Session(engine) as session:
        provider = DbSequenceProvider(session, "AO", "HUA")
        second_run = {
            item.building_id: item.postal_id
            for item in run_pipeline(grown, streets, "AO", "HUA", sequence_provider=provider)
        }
        session.commit()

    for building_id, postal_id in first_run.items():
        assert second_run[building_id] == postal_id, f"{building_id}'s postal ID was reassigned"
    assert "b0" in second_run
    assert second_run["b0"] not in first_run.values()


def test_db_sequence_provider_persists_across_separate_sessions(tmp_path):
    db_path = tmp_path / "sequence_persist.sqlite"
    engine = create_engine(f"sqlite:///{db_path}")
    PostalSequence.__table__.create(engine)

    with Session(engine) as session:
        seq_a = DbSequenceProvider(session, "AO", "LUA").next_sequence("bA")
        session.commit()

    with Session(engine) as session:
        seq_a_again = DbSequenceProvider(session, "AO", "LUA").next_sequence("bA")
        seq_b = DbSequenceProvider(session, "AO", "LUA").next_sequence("bB")
        session.commit()

    assert seq_a_again == seq_a
    assert seq_b != seq_a


def test_db_sequence_provider_rejects_building_id_reused_across_districts(tmp_path):
    db_path = tmp_path / "sequence_conflict.sqlite"
    engine = create_engine(f"sqlite:///{db_path}")
    PostalSequence.__table__.create(engine)

    with Session(engine) as session:
        DbSequenceProvider(session, "AO", "LUA").next_sequence("shared-id")
        session.commit()

    with Session(engine) as session:
        provider = DbSequenceProvider(session, "AO", "HUA")
        try:
            provider.next_sequence("shared-id")
            assert False, "expected a ValueError for a building_id reused across districts"
        except ValueError:
            pass
