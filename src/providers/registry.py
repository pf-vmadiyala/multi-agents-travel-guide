import os
from src.providers.base import (
    FlightSearchProvider,
    HotelSearchProvider,
    ActivityProvider,
    RestaurantProvider,
    WeatherProvider,
    SafetyProvider,
    MapsProvider
)
from src.providers.stub_providers import (
    StubFlightProvider,
    StubHotelProvider,
    StubActivityProvider,
    StubRestaurantProvider,
    StubWeatherProvider,
    StubSafetyProvider,
    StubMapsProvider
)

# ===== Registry Factory Resolvers =====

def get_flight_provider() -> FlightSearchProvider:
    """Resolve and instantiate the configured flight search provider."""
    provider = os.getenv("FLIGHT_PROVIDER", "stub").lower()
    if provider == "stub":
        return StubFlightProvider()
    # (Future providers like Amadeus/Duffel can be loaded here)
    return StubFlightProvider()


def get_hotel_provider() -> HotelSearchProvider:
    """Resolve and instantiate the configured hotel search provider."""
    provider = os.getenv("HOTEL_PROVIDER", "stub").lower()
    if provider == "stub":
        return StubHotelProvider()
    return StubHotelProvider()


def get_activity_provider() -> ActivityProvider:
    """Resolve and instantiate the configured activity search provider."""
    provider = os.getenv("ACTIVITY_PROVIDER", "stub").lower()
    if provider == "stub":
        return StubActivityProvider()
    return StubActivityProvider()


def get_restaurant_provider() -> RestaurantProvider:
    """Resolve and instantiate the configured restaurant search provider."""
    provider = os.getenv("RESTAURANT_PROVIDER", "stub").lower()
    if provider == "stub":
        return StubRestaurantProvider()
    return StubRestaurantProvider()


def get_weather_provider() -> WeatherProvider:
    """Resolve and instantiate the configured weather forecast provider."""
    provider = os.getenv("WEATHER_PROVIDER", "stub").lower()
    if provider == "stub":
        return StubWeatherProvider()
    return StubWeatherProvider()


def get_safety_provider() -> SafetyProvider:
    """Resolve and instantiate the configured safety advisory provider."""
    provider = os.getenv("SAFETY_PROVIDER", "stub").lower()
    if provider == "stub":
        return StubSafetyProvider()
    return StubSafetyProvider()


def get_maps_provider() -> MapsProvider:
    """Resolve and instantiate the configured geocoding/maps provider."""
    provider = os.getenv("MAPS_PROVIDER", "stub").lower()
    if provider == "stub":
        return StubMapsProvider()
    return StubMapsProvider()
