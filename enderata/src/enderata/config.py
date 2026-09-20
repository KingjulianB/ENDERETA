import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    country_code: str
    district_code: str
    aoi_district: str


def load_settings() -> Settings:
    return Settings(
        database_url=os.environ.get(
            "DATABASE_URL", "postgresql://postgres@localhost:5432/enderata"
        ),
        country_code=os.environ.get("COUNTRY_CODE", "AO"),
        district_code=os.environ.get("DISTRICT_CODE", "HUA"),
        aoi_district=os.environ.get("AOI_DISTRICT", "huambo"),
    )
