import random
from typing import List

from countryinfo import CountryInfo


class Country:
    name: str
    population: int
    size: float
    region: str
    languages: List[str]
    currencies: List[str]
    timezones: List[str]

    def __init__(self, name, population, size, region, languages, currencies, timezones):
        self.name = name
        self.population = population
        self.size = size
        self.region = region
        self.languages = languages
        self.currencies = currencies
        self.timezones = timezones


def map_to_country_obj(country_info_obj: CountryInfo) -> Country:
    info = country_info_obj.info()

    name = info.get("name", "")
    population = info.get("population", 0)
    size = info.get("area", 0.0)
    region = info.get("region", "")
    languages = info.get("languages", [])
    currencies = info.get("currencies", [])
    timezones = info.get("timezones", [])

    return Country(name, population, size, region, languages, currencies, timezones)


def get_random_country() -> Country:
    """
    Returns a random country object.
    """
    all_countries = CountryInfo().all()
    random_country_name = random.choice(list(all_countries.keys()))
    obj = CountryInfo(random_country_name)

    return map_to_country_obj(obj)


def get_country(name: str) -> Country:
    """
    Returns the country that matches the given name string, or None
    if no such country exists.
    """
    try:
        country = CountryInfo(name)
        return map_to_country_obj(country)
    except KeyError:
        return None
