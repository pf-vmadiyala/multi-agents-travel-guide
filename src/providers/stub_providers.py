import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# ===== 1. Stub Flight Search Provider =====
class StubFlightProvider:
    async def search_flights(
        self, origin: str, destination: str, departure_date: str, return_date: str, preferences: List[str]
    ) -> Dict[str, Any]:
        await asyncio.sleep(0.1)  # Simulate network latency
        return {
            "origin_iata": origin.upper()[:3],
            "destination_iata": destination.upper()[:3] if len(destination) >= 3 else "TUL",
            "flights": [
                {
                    "airline": "United Airlines",
                    "flight_number": "UA402",
                    "departure_time": "08:15",
                    "arrival_time": "10:30",
                    "price_usd": 240.00,
                    "duration": "2h 15m",
                    "stops": 0,
                    "type": "cheapest",
                    "why_recommended": "Direct morning flight, lowest price available."
                },
                {
                    "airline": "Delta Air Lines",
                    "flight_number": "DL1102",
                    "departure_time": "14:20",
                    "arrival_time": "16:35",
                    "price_usd": 280.00,
                    "duration": "2h 15m",
                    "stops": 0,
                    "type": "best_value",
                    "why_recommended": "Direct afternoon flight with premium cabin amenities."
                },
                {
                    "airline": "American Airlines",
                    "flight_number": "AA892",
                    "departure_time": "19:00",
                    "arrival_time": "21:10",
                    "price_usd": 310.00,
                    "duration": "2h 10m",
                    "stops": 0,
                    "type": "fastest",
                    "why_recommended": "Slightly shorter tailwind route arriving in the evening."
                }
            ]
        }

# ===== 2. Stub Hotel Search Provider =====
class StubHotelProvider:
    async def search_hotels(
        self, lat: float, lon: float, check_in: str, check_out: str, preferences: List[str]
    ) -> List[Dict[str, Any]]:
        await asyncio.sleep(0.1)
        # Calculates days of stay
        try:
            days = (datetime.strptime(check_out, "%Y-%m-%d") - datetime.strptime(check_in, "%Y-%m-%d")).days
        except Exception:
            days = 7

        return [
            {
                "name": "Panhandle Mountain Lodge",
                "address": "1234 Pine Street, Broken Bow, OK 74311",
                "star_rating": 4.8,
                "price_per_night_usd": 420.00,
                "total_cost_usd": float(420.00 * days),
                "latitude": lat,
                "longitude": lon,
                "tier": "luxury",
                "amenities": ["Hot Tub", "Fireplace", "Free Wifi"],
                "booking_url": "https://example.com/bookings/hotel-1"
            },
            {
                "name": "Broken Bow Cozy Cabins",
                "address": "800 Forest Road, Broken Bow, OK 74311",
                "star_rating": 4.5,
                "price_per_night_usd": 250.00,
                "total_cost_usd": float(250.00 * days),
                "latitude": lat + 0.005,
                "longitude": lon - 0.005,
                "tier": "moderate",
                "amenities": ["BBQ Grill", "Kitchen", "WiFi"],
                "booking_url": "https://example.com/bookings/hotel-2"
            }
        ]

# ===== 3. Stub Activity Provider =====
class StubActivityProvider:
    async def search_activities(
        self, lat: float, lon: float, interests: List[str]
    ) -> List[Dict[str, Any]]:
        await asyncio.sleep(0.1)
        return [
            {
                "name": "Little River Wildlife Hike",
                "category": "Outdoor Activity",
                "description": "Scenic guided hiking trail around the nature refuge.",
                "cost_usd": 0.00,
                "latitude": lat + 0.01,
                "longitude": lon - 0.01,
                "matching_interest": "hiking",
                "why_recommended": "Fits your hiking preference with local nature scenery."
            },
            {
                "name": "Broken Bow Lake Boating",
                "category": "Water Sports",
                "description": "Kayaking and canoeing at the lake marina.",
                "cost_usd": 45.00,
                "latitude": lat - 0.01,
                "longitude": lon + 0.01,
                "matching_interest": "nature",
                "why_recommended": "Allows water-based sightseeing in Oklahoma's forests."
            }
        ]

# ===== 4. Stub Restaurant Provider =====
class StubRestaurantProvider:
    async def search_restaurants(
        self, lat: float, lon: float, cuisines: List[str]
    ) -> List[Dict[str, Any]]:
        await asyncio.sleep(0.1)
        return [
            {
                "name": "Smith's Country Kitchen",
                "cuisine": "bbq",
                "address": "202 Main St, Broken Bow, OK",
                "description": "Locally renowned slow-smoked brisket and classic Southern sides.",
                "latitude": lat,
                "longitude": lon,
                "cost_per_person_usd": 22.00,
                "why_recommended": "Smoked BBQ restaurant aligned with your dining preferences."
            },
            {
                "name": "KJ's Espresso & Sweet Treats",
                "cuisine": "coffee",
                "address": "206 South Park Drive, Broken Bow, OK",
                "description": "Cozy local cafe offering fresh coffee roasts, pastries, and ice cream.",
                "latitude": lat + 0.002,
                "longitude": lon - 0.002,
                "cost_per_person_usd": 8.00,
                "why_recommended": "Local espresso cafe matching your request for coffee stops."
            }
        ]

# ===== 5. Stub Weather Provider =====
class StubWeatherProvider:
    async def get_forecast(self, lat: float, lon: float) -> List[Dict[str, Any]]:
        await asyncio.sleep(0.1)
        # Returns static 8-day forecast
        today = datetime.now()
        forecast = []
        for i in range(8):
            date_str = (today + timedelta(days=i)).strftime("%Y-%m-%d")
            # Create a sunny/cloudy alternating forecast
            desc = "Clear/Sunny (High: 92F, Low: 70F)" if i % 2 == 0 else "Partly Cloudy (High: 88F, Low: 68F)"
            forecast.append({
                "date": date_str,
                "description": desc,
                "temperature": 81 if i % 2 == 0 else 78,
                "rainfall_mm": 0.0 if i % 2 == 0 else 1.2,
                "outdoor_feasible": True
            })
        return forecast

# ===== 6. Stub Safety Provider =====
class StubSafetyProvider:
    async def get_safety_report(self, country_code: str) -> Dict[str, Any]:
        await asyncio.sleep(0.1)
        return {
            "destination": f"Country code: {country_code.upper()}",
            "advisory_level": "low",
            "advisory_source": "State Department (Mock Stub Database)",
            "advisory_summary": "General low risk area. Normal safety precautions apply. Avoid late-night isolated areas.",
            "local_emergency_numbers": {
                "police": "911" if country_code.upper() in ["US", "CA"] else "112",
                "ambulance": "911" if country_code.upper() in ["US", "CA"] else "112"
            }
        }

# ===== 7. Stub Maps Provider =====
class StubMapsProvider:
    async def geocode(self, location_name: str) -> Optional[Dict[str, Any]]:
        await asyncio.sleep(0.1)
        # Standard mock coordinates for testing
        return {
            "latitude": 34.0298,
            "longitude": -94.7391,
            "country_code": "US",
            "country": "United States"
        }
