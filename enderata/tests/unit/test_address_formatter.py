from enderata.numbering.address_formatter import format_address


def test_format_address_matches_expected_layout():
    assert format_address("Rua da Missao", 24, "Huambo") == "Rua da Missao, 24, Huambo, Angola"
