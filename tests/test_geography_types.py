from backend.geography.types import RegionType


def test_region_type_values_match_data_model() -> None:
    assert RegionType.values() == {
        "city",
        "metro",
        "greater_region",
        "state",
        "custom_region",
    }


def test_region_type_str_enum_round_trip() -> None:
    assert RegionType("greater_region") is RegionType.GREATER_REGION
    assert RegionType.GREATER_REGION.value == "greater_region"
