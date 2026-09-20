"""Compose the human-readable address layer on top of a permanent postal ID.

The postal ID never appears in this string by design (business plan
section 3.2, "separate the ID from the address"): the readable address
can be re-ordered or renamed later without ever touching the ID it is
displayed alongside.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Address:
    street_name: str
    number: int
    district: str
    country: str = "Angola"

    def __str__(self) -> str:
        return f"{self.street_name}, {self.number}, {self.district}, {self.country}"


def format_address(street_name: str, number: int, district: str) -> str:
    return str(Address(street_name=street_name, number=number, district=district))
