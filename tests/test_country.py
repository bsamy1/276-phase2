from countryinfo import CountryInfo

from phase2.country import Country, get_country, get_random_country, map_to_country_obj


def test_map_to_country_obj():
    obj = CountryInfo("Canada")
    info = obj.info()

    country = map_to_country_obj(obj)

    assert isinstance(country, Country)

    assert country.name == info.get("name", "")
    assert country.population == info.get("population", 0)
    assert country.size == info.get("area", 0.0)


def test_get_country_valid_name():
    country = get_country("Canada")

    assert isinstance(country, Country)
    assert country.name == "Canada"


def test_get_country_invalid_name():
    country = get_country("ABCXYZ")

    assert country is None


def test_get_random_country():
    country = get_random_country()

    assert isinstance(country, Country)
    assert country.name != ""
    assert isinstance(country.currencies, list)
