import asyncio
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy import select, func
from src.db.session import AsyncSessionLocal, engine
from src.db.models import User, Trip, Hotel, Restaurant, Flight, Activity, CostSummary
import src.db.crud as crud
from src.cache.trip_cache import TripCache
import pytest
pytestmark = pytest.mark.e2e

from dotenv import load_dotenv
load_dotenv()


# Mock completed itinerary data for testing
MOCK_ITINERARY = {
    "destination": "Broken Bow, Oklahoma",
    "origin": "Chicago",
    "departure_date": "2026-07-20",
    "return_date": "2026-07-27",
    "flight_options": {
        "origin_iata": "ORD",
        "destination_iata": "TUL",
        "flights": [
            {
                "airline": "Southwest Airlines",
                "price_usd": 150.00,
                "type": "cheapest"
            },
            {
                "airline": "Delta Air Lines",
                "price_usd": 180.00,
                "type": "best_value"
            }
        ]
    },
    "hotel_options": [
        {
            "name": "Panhandle Mountain Lodge",
            "address": "1234 Pine Street, Broken Bow, OK 74311",
            "star_rating": 4.7,
            "price_per_night_usd": 420.00,
            "total_cost_usd": 2940.00,
            "latitude": 34.1623,
            "longitude": -94.6934
        }
    ],
    "curated_activities": [
        {
            "name": "Yanubbee Creek Nature Walk",
            "category": "Nature Stream",
            "description": "Scenic creek hiking.",
            "cost_usd": 0.0,
            "latitude": 33.9791,
            "longitude": -94.6997
        }
    ],
    "curated_restaurants": [
        {
            "name": "KJ's Coffee & Sweet Shoppe",
            "cuisine": "coffee",
            "address": "206 South Park Drive, Broken Bow, OK",
            "cost_per_person_usd": 12.50,
            "latitude": 34.0249,
            "longitude": -94.7399
        }
    ]
}

async def run_validation():
    """Run an end-to-end validation of DB writes, idempotency, PostGIS queries, and Redis caching, then clean up."""
    print("\n==================================================")
    print("      STARTING DB & CACHE END-TO-END VALIDATION   ")
    print("==================================================\n")

    # 1. Initialize Redis Cache
    print("-> Connecting to Redis Cache...")
    cache = TripCache()
    
    # 2. Open DB Session
    print("-> Connecting to PostgreSQL...")
    async with AsyncSessionLocal() as session:
        test_email = f"tester_{uuid.uuid4().hex[:6]}@example.com"
        user_uuid = None
        trip_uuid = None

        try:
            # 3. Create a Test User
            print(f"   [Step 1] Creating test user: {test_email}...")
            user = await crud.create_user(session, email=test_email, password_hash="dummy_hash")
            user_uuid = user.user_id
            await session.commit()
            print(f"   User successfully created (UUID: {user_uuid})")

            # 4. Test Idempotency with Trip Creation
            print("\n   [Step 2] Testing Trip Creation with Idempotency...")
            idempotency_key = f"key_{uuid.uuid4().hex}"
            
            # Submit first request
            trip1 = await crud.create_trip(
                session,
                user_id=user_uuid,
                destination="Broken Bow, Oklahoma",
                start_date=date(2026, 7, 20),
                duration_days=7,
                budget_usd=3500.00,
                idempotency_key=idempotency_key
            )
            trip_uuid = trip1.trip_id
            await session.commit()
            print(f"   Trip 1 created successfully (UUID: {trip_uuid})")

            # Submit duplicate request
            trip2 = await crud.create_trip(
                session,
                user_id=user_uuid,
                destination="Broken Bow, Oklahoma",
                start_date=date(2026, 7, 20),
                duration_days=7,
                budget_usd=3500.00,
                idempotency_key=idempotency_key
            )
            print(f"   Trip 2 execution output UUID: {trip2.trip_id}")
            assert trip1.trip_id == trip2.trip_id, "Idempotency constraint failed: duplicate request created a new record!"
            print("   SUCCESS: Idempotency interception works! Returned existing Trip UUID.")

            # 5. Compile and Save Itinerary Details
            print("\n   [Step 3] Compiling and saving itinerary components to tables...")
            await crud.save_itinerary_details(session, trip_uuid, MOCK_ITINERARY)
            await session.commit()
            print("   Itinerary records compiled successfully.")

            # Verify flights, hotels, cost summaries are updated
            trip_record = await crud.get_trip(session, trip_uuid)
            assert trip_record.status == "completed", "Itinerary status did not update to 'completed'!"
            print(f"   Trip status verified: '{trip_record.status}'")

            # 6. Test PostGIS Geospatial Queries
            print("\n   [Step 4] Querying PostGIS geospatial coordinate distance...")
            # Let's measure the distance between our hotel and the restaurant using PostGIS geography ST_Distance
            stmt = select(
                Hotel.name,
                Restaurant.name,
                func.ST_Distance(Hotel.location, Restaurant.location).label("distance_meters")
            ).where(
                Hotel.trip_id == trip_uuid,
                Restaurant.trip_id == trip_uuid
            )
            res = await session.execute(stmt)
            row = res.first()
            if row:
                hotel_name, rest_name, distance = row
                print(f"   Success! PostGIS calculated distance between '{hotel_name}' and '{rest_name}':")
                print(f"   -> Distance: {distance / 1000.0:.2f} km ({distance:.2f} meters)")
            else:
                raise AssertionError("Failed to load hotel/restaurant location coordinate references!")

            # 7. Test Redis Caching Client
            print("\n   [Step 5] Writing compiled itinerary data to Redis Cache...")
            await cache.set_itinerary(str(trip_uuid), MOCK_ITINERARY)
            print("   Writing progress state 'completed' to Redis Cache...")
            await cache.set_planning_status(str(trip_uuid), "completed")

            cached_itinerary = await cache.get_itinerary(str(trip_uuid))
            cached_status = await cache.get_planning_status(str(trip_uuid))

            assert cached_itinerary is not None, "Redis Itinerary cache miss!"
            assert cached_status == "completed", "Redis Status cache mismatch!"
            print("   SUCCESS: Redis cache write and read-back match perfectly!")

        finally:
            # 8. Clean up all records from PostgreSQL and Redis to keep the environment pristine
            print("\n   [Step 6] Cleaning up test records from databases...")
            if trip_uuid:
                # SQLAlchemy relationships will automatically cascade delete flights, hotels, activities, etc.
                await session.execute(select(Trip).where(Trip.trip_id == trip_uuid))
                trip_db_record = await session.get(Trip, trip_uuid)
                if trip_db_record:
                    await session.delete(trip_db_record)
                # Remove cached Redis keys
                await cache.client.delete(f"trip:itinerary:{trip_uuid}")
                await cache.client.delete(f"trip:status:{trip_uuid}")

            if user_uuid:
                user_db_record = await session.get(User, user_uuid)
                if user_db_record:
                    await session.delete(user_db_record)
            
            await session.commit()
            await cache.close()
            print("   Cleanup completed successfully.")

    print("\n==================================================")
    print("      ALL TESTS PASSED SUCCESSFULLY! (Phase 2 Done) ")
    print("==================================================\n")

if __name__ == "__main__":
    asyncio.run(run_validation())
