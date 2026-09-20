"""Permanent postal identifier generation.

Format: <COUNTRY(2)><DISTRICT(3)><SEQUENCE(6)><CHECK(2)>
e.g. AOHUA00000198

The check digits use an ISO 7064 MOD 97-10 style checksum (the same
family of algorithm IBAN uses), so a single mistyped or transposed
character is caught. Once issued, an ID is never regenerated or
reassigned: the sequence number must come from a persistent counter,
not from array position or re-derived from geometry.
"""

from __future__ import annotations

_ALPHABET_OFFSET = 55  # 'A' -> 10, per ISO 7064 letter-to-digit mapping


def _letters_to_digits(value: str) -> str:
    digits = []
    for ch in value:
        if ch.isdigit():
            digits.append(ch)
        else:
            digits.append(str(ord(ch.upper()) - _ALPHABET_OFFSET))
    return "".join(digits)


def _mod97(numeric_string: str) -> int:
    remainder = 0
    for ch in numeric_string:
        remainder = (remainder * 10 + int(ch)) % 97
    return remainder


def _checksum(body: str) -> str:
    rearranged = f"{body}00"
    check = 98 - _mod97(_letters_to_digits(rearranged))
    return f"{check:02d}"


def generate_postal_id(country_code: str, district_code: str, sequence: int) -> str:
    if not (1 <= sequence <= 999_999):
        raise ValueError("sequence must be between 1 and 999999")
    if len(country_code) != 2 or not country_code.isalpha():
        raise ValueError("country_code must be a 2-letter ISO code")
    if len(district_code) != 3 or not district_code.isalpha():
        raise ValueError("district_code must be a 3-letter code")

    body = f"{country_code.upper()}{district_code.upper()}{sequence:06d}"
    return f"{body}{_checksum(body)}"


def is_valid_postal_id(postal_id: str) -> bool:
    if len(postal_id) != 13:
        return False
    body, check = postal_id[:-2], postal_id[-2:]
    return _checksum(body) == check
