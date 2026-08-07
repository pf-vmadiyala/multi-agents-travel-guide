import os
import json
from typing import Optional, Any
import redis.asyncio as redis

class TripCache:
    """
    Async Redis cache wrapper for caching compiled itineraries 
    and polling status of in-progress travel plans.
    """
    def __init__(self):
        """Initialize the async Redis client from the REDIS_URL environment variable."""
        # Load Redis connection URL from environment (defaults to DB 0)
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.client = redis.from_url(self.redis_url, decode_responses=True)

    async def set_itinerary(self, trip_id: str, itinerary: dict, expire_seconds: int = 86400) -> None:
        """
        Cache a completed travel itinerary JSON block. Default expiry is 24 hours.
        """
        key = f"trip:itinerary:{trip_id}"
        await self.client.set(key, json.dumps(itinerary), ex=expire_seconds)

    async def get_itinerary(self, trip_id: str) -> Optional[dict]:
        """
        Retrieve a cached itinerary. Returns None if cache missed.
        """
        key = f"trip:itinerary:{trip_id}"
        data = await self.client.get(key)
        if data:
            return json.loads(data)
        return None

    async def set_planning_status(self, trip_id: str, status: str, expire_seconds: int = 3600) -> None:
        """
        Set the in-progress planning status (e.g. 'planning', 'completed', 'failed').
        Default expiry is 1 hour.
        """
        key = f"trip:status:{trip_id}"
        await self.client.set(key, status, ex=expire_seconds)

    async def get_planning_status(self, trip_id: str) -> Optional[str]:
        """
        Fetch the current planning status.
        """
        key = f"trip:status:{trip_id}"
        return await self.client.get(key)

    async def close(self) -> None:
        """
        Close the Redis connection pool.
        """
        await self.client.aclose()
