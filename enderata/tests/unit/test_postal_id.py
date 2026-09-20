import pytest

from enderata.numbering.postal_id import generate_postal_id, is_valid_postal_id


def test_generate_postal_id_has_expected_length_and_prefix():
    postal_id = generate_postal_id("AO", "HUA", 1)
    assert len(postal_id) == 13
    assert postal_id.startswith("AOHUA000001")


def test_generate_postal_id_is_deterministic():
    assert generate_postal_id("AO", "HUA", 42) == generate_postal_id("AO", "HUA", 42)


def test_different_sequences_produce_different_ids():
    assert generate_postal_id("AO", "HUA", 1) != generate_postal_id("AO", "HUA", 2)


def test_generated_id_validates():
    postal_id = generate_postal_id("AO", "HUA", 123)
    assert is_valid_postal_id(postal_id)


def test_transposed_digit_fails_validation():
    # MOD 97-10 (the family IBAN uses) is guaranteed to catch a single
    # transposition of two adjacent, distinct digits -- the most common
    # real-world transcription error -- unlike a coincidental corruption
    # that has a ~1/97 chance of landing on another valid checksum.
    postal_id = generate_postal_id("AO", "HUA", 123456)
    chars = list(postal_id)
    chars[6], chars[7] = chars[7], chars[6]
    corrupted = "".join(chars)

    assert corrupted != postal_id
    assert not is_valid_postal_id(corrupted)


def test_rejects_invalid_sequence_range():
    with pytest.raises(ValueError):
        generate_postal_id("AO", "HUA", 0)
