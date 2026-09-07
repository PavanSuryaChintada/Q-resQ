from config import LANGUAGES, REGION


def test_region_is_aizawl():
    assert REGION["name"] == "Aizawl district, Mizoram"
    assert REGION["bbox"] == {"west": 92.55, "south": 23.55, "east": 93.05, "north": 24.05}
    assert REGION["grid_m"] == 100
    assert REGION["utm"] == "EPSG:32646"
    assert REGION["hq"] == (23.7271, 92.7176)


def test_languages_are_three_only():
    assert LANGUAGES == ["en", "hi", "as"]
