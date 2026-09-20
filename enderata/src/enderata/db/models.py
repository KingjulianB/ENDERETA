"""SQLAlchemy models for the PostGIS-backed ENDERETA registry.

Call `Base.metadata.create_all(engine)` to provision the schema for the
POC; a proper migration tool (Alembic) should replace this once the
schema needs to evolve without dropping data.
"""

from __future__ import annotations

from geoalchemy2 import Geometry
from sqlalchemy import Column, Float, ForeignKey, Integer, String
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
