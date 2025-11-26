import logging
import random
from typing import List

from countryinfo import CountryInfo

logger = logging.getLogger("phase2.country")


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
    name = country_info_obj.name()
    population = country_info_obj.population()
    size = country_info_obj.area()
    region = country_info_obj.region()
    languages = country_info_obj.languages()
    currencies = country_info_obj.currencies()
    timezones = country_info_obj.timezones()

    return Country(name, population, size, region, languages, currencies, timezones)


def get_random_country() -> Country:
    """
    Returns a random country object.
    """
    all_countries = CountryInfo().all()
    random_country_name = random.choice(list(all_countries.keys()))
    obj = CountryInfo(random_country_name)

    if not verify_country(obj):
        logger.warning("Daily country missing required info. Regenerating...")
        return get_random_country()  # run again if the random country is missing info

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


def verify_country(country) -> bool:
    """
    Verifies that a CountryInfo object from the api has all the required data for the game
    """
    props = ["name", "population", "area", "region", "languages", "currencies", "timezones"]
    return all(country.info().get(key) is not None for key in props)
