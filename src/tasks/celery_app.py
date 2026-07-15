import os
import asyncio
import uuid
from celery import Celery
from dotenv import load_dotenv

# Load env variables so Celery worker process inherits configs
load_dotenv()

# Load broker URL (defaults to Redis DB 1 to isolate it from the main cache DB 0)
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")

# Instantiate Celery Application
celery_app = Celery(
    "travel_planner",
    broker=CELERY_BROKER_URL,
    backend=CELERY_BROKER_URL
)

# Configure Celery serialization formats
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)


# ===== 1. ASYNC EXECUTOR BRIDGE =====

async def _async_orchestrate(
    trip_id: str,
    destination: str,
    origin: str,
    departure_date: str,
    return_date: str,
    interests: list,
    cuisines: list,
    travel_style: str,
    flight_preferences: list
):
    """Async wrapper executed inside the Celery worker process loop."""
    from src.orchestration.workflow import travel_planner_app
    from src.db.session import AsyncSessionLocal
    import src.db.crud as crud
    from src.cache.trip_cache import TripCache

    # Adapt parameters to match the StateGraph's inputs
    inputs = {
        "destination": destination,
        "origin": origin,
        "departure_date": departure_date,
        "return_date": return_date,
        "interests": interests,
        "cuisines": cuisines,
        "travel_style": [travel_style] if isinstance(travel_style, str) else travel_style,
        "flight_preferences": flight_preferences
    }

    try:
        print(f"\n[Celery Worker] Starting LangGraph planning for Trip: {trip_id} ({destination})")
        
        # Dispose of the global engine pool to bind it to the current event loop
        from src.db.session import engine
        await engine.dispose()
        
        # 1. Invoke the LangGraph Orchestrator
        # This will query weather, safety, flights, hotels, activities, and restaurants concurrently!
        config = {
            "run_name": f"{origin}-{destination}-{departure_date} to {return_date}",
            "metadata": {
                "trip_id": trip_id,
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date,
                "return_date": return_date
            }
        }
        final_state = await travel_planner_app.ainvoke(inputs, config=config)
        compiled_itinerary = final_state.get("compiled_itinerary")
        
        if not compiled_itinerary:
            raise ValueError("LangGraph compilation failed: Itinerary returned empty.")

        # 2. Persist the results in PostgreSQL
        print(f"[Celery Worker] Writing itinerary details to PostgreSQL...")
        async with AsyncSessionLocal() as session:
            await crud.save_itinerary_details(session, uuid.UUID(trip_id), compiled_itinerary)
            await session.commit()

        # 3. Cache the completed itinerary in Redis for fast loading
        print(f"[Celery Worker] Caching final itinerary in Redis L2...")
        cache = TripCache()
        await cache.set_itinerary(trip_id, compiled_itinerary)
        await cache.set_planning_status(trip_id, "completed")
        await cache.close()
        
        print(f"[Celery Worker] SUCCESS: Planning complete for Trip: {trip_id}\n")

    except Exception as err:
        print(f"\n[Celery Worker] ERROR: Failed planning for Trip {trip_id}: {str(err)}")
        
        # Mark status as failed in PostgreSQL
        from src.db.session import AsyncSessionLocal
        import src.db.crud as crud
        try:
            async with AsyncSessionLocal() as session:
                await crud.update_trip_status(session, uuid.UUID(trip_id), status="failed")
                await session.commit()
        except Exception as db_err:
            print(f"[Celery Worker] DB status update failed: {str(db_err)}")

        # Mark status as failed in Redis Cache
        try:
            cache = TripCache()
            await cache.set_planning_status(trip_id, "failed")
            await cache.close()
        except Exception as cache_err:
            print(f"[Celery Worker] Redis status update failed: {str(cache_err)}")
            
        raise err


# ===== 2. SYNCHRONOUS CELERY TASK DEF =====

@celery_app.task(name="tasks.orchestrate_travel_plan")
def orchestrate_travel_plan(
    trip_id: str,
    destination: str,
    origin: str,
    departure_date: str,
    return_date: str,
    interests: list,
    cuisines: list,
    travel_style: str,
    flight_preferences: list
):
    """Synchronous Celery task handler that starts the async loop."""
    asyncio.run(_async_orchestrate(
        trip_id,
        destination,
        origin,
        departure_date,
        return_date,
        interests,
        cuisines,
        travel_style,
        flight_preferences
    ))
