from countryinfo import CountryInfo

from phase2.country import Country, get_country, get_random_country, map_to_country_obj


def test_map_to_country_obj():
    obj = CountryInfo("Canada")

    country = map_to_country_obj(obj)

    assert isinstance(country, Country)

    assert country.name == obj.name()
    assert country.population == obj.population()
    assert country.size == obj.area()


def test_get_country_valid_name():
    country = get_country("Canada")

    assert isinstance(country, Country)
    assert country.name == "canada"


def test_get_country_invalid_name():
    country = get_country("ABCXYZ")

    assert country is None


def test_get_random_country():
    country = get_random_country()

    assert isinstance(country, Country)
    assert country.name != ""
