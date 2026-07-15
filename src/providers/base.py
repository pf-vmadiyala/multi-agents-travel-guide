from typing import Protocol, List, Dict, Any, Optional

class FlightSearchProvider(Protocol):
    """Protocol defining search interface for flight options."""
    async def search_flights(
        self, 
        origin: str, 
        destination: str, 
        departure_date: str, 
        return_date: str, 
        preferences: List[str]
    ) -> Dict[str, Any]:
        ...

class HotelSearchProvider(Protocol):
    """Protocol defining search interface for lodging/hotel options."""
    async def search_hotels(
        self, 
        lat: float, 
        lon: float, 
        check_in: str, 
        check_out: str, 
        preferences: List[str]
    ) -> List[Dict[str, Any]]:
        ...

class ActivityProvider(Protocol):
    """Protocol defining search interface for local sights and activities."""
    async def search_activities(
        self, 
        lat: float, 
        lon: float, 
        interests: List[str]
    ) -> List[Dict[str, Any]]:
        ...

class RestaurantProvider(Protocol):
    """Protocol defining search interface for dining options."""
    async def search_restaurants(
        self, 
        lat: float, 
        lon: float, 
        cuisines: List[str]
    ) -> List[Dict[str, Any]]:
        ...

class WeatherProvider(Protocol):
    """Protocol defining interface for retrieving local weather forecasts."""
    async def get_forecast(self, lat: float, lon: float) -> List[Dict[str, Any]]:
        ...

class SafetyProvider(Protocol):
    """Protocol defining interface for retrieving country safety data."""
    async def get_safety_report(self, country_code: str) -> Dict[str, Any]:
        ...

class MapsProvider(Protocol):
    """Protocol defining interface for geocoding address locations."""
    async def geocode(self, location_name: str) -> Optional[Dict[str, Any]]:
        ...
