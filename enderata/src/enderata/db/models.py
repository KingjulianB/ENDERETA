"""SQLAlchemy models for the PostGIS-backed ENDERETA registry.

Call `Base.metadata.create_all(engine)` to provision the schema for the
POC; a proper migration tool (Alembic) should replace this once the
schema needs to evolve without dropping data.
"""

from __future__ import annotations

from geoalchemy2 import Geometry
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Street(Base):
    __tablename__ = "streets"

    id = Column(String, primary_key=True)
    osm_way_id = Column(String, nullable=True)
    name = Column(String, nullable=False)
    geometry = Column(Geometry(geometry_type="LINESTRING", srid=4326), nullable=False)

    buildings = relationship("Building", back_populates="street")


class Building(Base):
    __tablename__ = "buildings"

    id = Column(String, primary_key=True)
    source = Column(String, nullable=False)  # "open_buildings" | "osm"
    geometry = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    street_id = Column(String, ForeignKey("streets.id"), nullable=True)
    distance_along_street = Column(Float, nullable=True)
    side = Column(String, nullable=True)  # "even" | "odd"

    street = relationship("Street", back_populates="buildings")
    address = relationship("BuildingAddress", back_populates="building", uselist=False)


class BuildingAddress(Base):
    __tablename__ = "addresses"

    building_id = Column(String, ForeignKey("buildings.id"), primary_key=True)
    postal_id = Column(String, unique=True, nullable=False)
    house_number = Column(Integer, nullable=False)
    display_address = Column(String, nullable=False)

    building = relationship("Building", back_populates="address")


class PostalSequence(Base):
    """Persistent postal-ID sequence counter, keyed by building_id --
    see numbering/sequence.py's DbSequenceProvider. No geometry column
    (unlike Street/Building/BuildingAddress above), so this table can
    be created and tested against plain SQLite, not just PostGIS.
    """

    __tablename__ = "postal_sequences"

    building_id = Column(String, primary_key=True)
    country_code = Column(String, nullable=False)
    district_code = Column(String, nullable=False)
    sequence_number = Column(Integer, nullable=False)
    assigned_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("country_code", "district_code", "sequence_number"),
    )
