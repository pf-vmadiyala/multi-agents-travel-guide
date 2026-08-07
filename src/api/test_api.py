import asyncio
import uuid
import httpx
from datetime import date, timedelta
from sqlalchemy import select
from src.db.session import AsyncSessionLocal
from src.db.models import User, Trip

API_URL = "http://localhost:8000/api/v1"

async def test_flow():
    """Run an end-to-end REST API integration test: register, login, plan a trip, poll, and verify results."""
    print("\n==================================================")
    print("      STARTING REST API END-TO-END INTEGRATION   ")
    print("==================================================\n")

    async with httpx.AsyncClient() as client:
        # 1. Check Liveness / Readiness
        print("-> Checking API Health status...")
        res = await client.get(f"{API_URL.replace('/api/v1', '')}/")
        assert res.status_code == 200, "App failed liveness check!"
        
        ready_res = await client.get(f"{API_URL}/health/ready")
        assert ready_res.status_code == 200, f"App readiness check failed: {ready_res.text}"
        print("   API Health is 100% OK.")

        # 2. Register a New Test User
        test_email = f"api_tester_{uuid.uuid4().hex[:6]}@example.com"
        test_password = "SecurePassword123"
        print(f"\n[Step 1] Registering test user: {test_email}...")
        
        reg_res = await client.post(
            f"{API_URL}/auth/register",
            json={"email": test_email, "password": test_password}
        )
        assert reg_res.status_code == 201, f"Registration failed: {reg_res.text}"
        user_id = reg_res.json()["user_id"]
        print(f"   User registered (UUID: {user_id})")

        # 3. Log In to Retrieve JWT Access Token
        print("\n[Step 2] Logging in to retrieve JWT access token...")
        login_res = await client.post(
            f"{API_URL}/auth/token",
            data={"username": test_email, "password": test_password}
        )
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("   JWT Token retrieved successfully.")

        # 4. Submit Trip Planning Request (Queued in Celery)
        print("\n[Step 3] Submitting trip plan request for Broken Bow, Oklahoma...")
        today = date.today()
        departure = today + timedelta(days=5)
        returning = today + timedelta(days=10)
        
        req_payload = {
            "destination": "Broken Bow, Oklahoma",
            "origin": "Chicago",
            "departure_date": str(departure),
            "return_date": str(returning),
            "budget_usd": 2500.00,
            "travel_style": "luxury",
            "party_size": 2,
            "interests": ["hiking", "nature"],
            "cuisines": ["coffee", "bbq"]
        }
        
        plan_res = await client.post(
            f"{API_URL}/plan",
            json=req_payload,
            headers=headers
        )
        assert plan_res.status_code == 202, f"Plan request failed: {plan_res.text}"
        trip_id = plan_res.json()["trip_id"]
        print(f"   Trip planning queued in Celery (Trip ID: {trip_id})")

        # 5. Poll Status endpoint until completion
        print("\n[Step 4] Polling trip status (waiting for Celery worker and LLM)...")
        max_attempts = 400
        completed = False
        
        for attempt in range(1, max_attempts + 1):
            status_res = await client.get(f"{API_URL}/status/{trip_id}", headers=headers)
            assert status_res.status_code == 200, f"Status check failed: {status_res.text}"
            status_val = status_res.json()["status"]
            print(f"   -> Check #{attempt}: Status is '{status_val}'")
            
            if status_val == "completed":
                completed = True
                break
            elif status_val == "failed":
                raise AssertionError("Celery planning task failed in background!")
                
            await asyncio.sleep(4) # Wait 4 seconds before polling again
            
        assert completed, "Task timed out before completion!"

        # 6. Verify IDOR Access Security (Forbidden with other token)
        print("\n[Step 5] Testing IDOR Security prevention...")
        fake_headers = {"Authorization": "Bearer fake-token-key-here"}
        fake_res = await client.get(f"{API_URL}/trips/{trip_id}", headers=fake_headers)
        assert fake_res.status_code == 401, f"Expected 401 for fake token, got: {fake_res.status_code}"
        print("   SUCCESS: Endpoint blocked unauthorized request with 401.")

        # 7. Fetch Finalized Itinerary Details
        print("\n[Step 6] Loading completed itinerary...")
        itinerary_res = await client.get(f"{API_URL}/trips/{trip_id}", headers=headers)
        assert itinerary_res.status_code == 200, f"Failed to get itinerary: {itinerary_res.text}"
        itinerary = itinerary_res.json()
        
        print("\n=== COMPILED PLAN SUMMARY ===")
        print(f"Destination: {itinerary.get('destination')}")
        print(f"Start Date:  {itinerary.get('departure_date')}")
        print(f"Cost Summary: {itinerary.get('cost_summary')}")
        print("=============================\n")

        # 8. Clean up database records
        print("[Step 7] Cleaning up test records from database...")
        async with AsyncSessionLocal() as session:
            # SQLAlchemy relationships will cascade delete related flights/hotels/etc.
            trip_uuid = uuid.UUID(trip_id)
            trip_db = await session.get(Trip, trip_uuid)
            if trip_db:
                await session.delete(trip_db)
            
            user_uuid = uuid.UUID(user_id)
            user_db = await session.get(User, user_uuid)
            if user_db:
                await session.delete(user_db)
                
            await session.commit()
            
        # Clean Redis keys
        import redis.asyncio as redis
        redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        await redis_client.delete(f"trip:itinerary:{trip_id}")
        await redis_client.delete(f"trip:status:{trip_id}")
        await redis_client.aclose()
        print("   Cleanup successful.")

    print("\n==================================================")
    print("      ALL API TESTS PASSED SUCCESSFULLY!          ")
    print("==================================================\n")

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(test_flow())
