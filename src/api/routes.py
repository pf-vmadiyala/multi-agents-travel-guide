import uuid
from datetime import date
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.db.models import User, Trip, Flight, Hotel, Activity, Restaurant, CostSummary
import src.db.crud as crud
from src.api.models import UserCreateRequest, TokenResponse, TripPlanRequest, TripPlanResponse, TripStatusResponse
from src.api.auth import get_password_hash, verify_password, create_access_token, get_current_user, require_trip_ownership
from src.cache.trip_cache import TripCache
from src.utils.errors import ConflictError, NotFoundError

# We will define the Celery task inside src/tasks/celery_app.py
from src.tasks.celery_app import orchestrate_travel_plan

router = APIRouter()


# ==========================================
# ===== 1. AUTHENTICATION ENDPOINTS =====
# ==========================================

@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register_user(payload: UserCreateRequest, db: AsyncSession = Depends(get_db)):
    """Registers a new user in the system."""
    existing_user = await crud.get_user_by_email(db, payload.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this email already exists.")
        
    pwd_hash = get_password_hash(payload.password)
    user = await crud.create_user(db, payload.email, pwd_hash)
    await db.commit()
    return {"message": "User registered successfully.", "user_id": str(user.user_id)}


@router.post("/auth/token", response_model=TokenResponse)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: AsyncSession = Depends(get_db)
):
    """OAuth2 password flow token exchange."""
    user = await crud.get_user_by_email(db, form_data.username)
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = create_access_token(data={"sub": str(user.user_id)})
    return TokenResponse(access_token=access_token)


# ==========================================
# ===== 2. TRIP PLANNING ENDPOINTS =====
# ==========================================

@router.post("/plan", response_model=TripPlanResponse, status_code=status.HTTP_202_ACCEPTED)
async def plan_trip(
    payload: TripPlanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Submits a trip planning request. Checks for duplicate requests via idempotency key,
    writes a pending database record, and queues the LangGraph task in Celery.
    """
    # 1. Enforce idempotency and create Trip record
    idempotency_key = f"plan_{payload.destination.replace(' ', '_')}_{payload.departure_date}"
    
    trip = await crud.create_trip(
        db,
        user_id=current_user.user_id,
        destination=payload.destination,
        start_date=payload.departure_date,
        duration_days=(payload.return_date - payload.departure_date).days,
        budget_usd=payload.budget_usd,
        travel_style=payload.travel_style,
        party_size=payload.party_size,
        idempotency_key=idempotency_key
    )
    await db.commit()

    # 2. Check if the trip was already completed or is currently running
    cache = TripCache()
    status_state = await cache.get_planning_status(str(trip.trip_id))
    
    if status_state in ["planning", "completed"]:
        return TripPlanResponse(trip_id=trip.trip_id, status=status_state, message="Trip already queued/planned.")

    # 3. Cache status as planning and dispatch worker task
    await cache.set_planning_status(str(trip.trip_id), "planning")
    await cache.close()

    orchestrate_travel_plan.delay(
        str(trip.trip_id),
        payload.destination,
        payload.origin,
        str(payload.departure_date),
        str(payload.return_date),
        payload.interests,
        payload.cuisines,
        payload.travel_style,
        payload.flight_preferences
    )

    return TripPlanResponse(trip_id=trip.trip_id, status="planning")


@router.get("/status/{trip_id}", response_model=TripStatusResponse)
async def get_trip_status(
    trip_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Polls the status of a trip planning task."""
    # Enforce ownership before responding
    trip = await crud.get_trip(db, trip_id)
    if not trip:
        raise NotFoundError("Trip not found.")
    if trip.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this trip.")

    # Try cache first
    cache = TripCache()
    cached_status = await cache.get_planning_status(str(trip_id))
    await cache.close()

    if cached_status:
        return TripStatusResponse(trip_id=trip_id, status=cached_status)

    return TripStatusResponse(trip_id=trip_id, status=trip.status)


@router.get("/trips")
async def get_user_trips(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve all trips owned by the authenticated user."""
    trips = await crud.get_trips_by_user(db, current_user.user_id)
    return [
        {
            "trip_id": str(t.trip_id),
            "destination": t.destination,
            "start_date": str(t.start_date),
            "duration_days": t.duration_days,
            "budget_usd": float(t.budget_usd),
            "status": t.status,
            "created_at": t.created_at.isoformat() if t.created_at else None
        }
        for t in trips
    ]


@router.get("/trips/{trip_id}")
async def get_completed_itinerary(
    trip_id: uuid.UUID,
    trip: Trip = Depends(require_trip_ownership),
    db: AsyncSession = Depends(get_db)
):
    """Fetches a completed travel plan. Uses Redis caching for instant retrieval."""
    cache = TripCache()
    
    # 1. Try L2 Redis cache
    cached_itinerary = await cache.get_itinerary(str(trip_id))
    if cached_itinerary:
        await cache.close()
        return cached_itinerary

    # 2. Cache miss: Read from database and construct the dictionary
    if trip.status != "completed":
        await cache.close()
        return {"trip_id": trip_id, "status": trip.status, "message": "Itinerary is not ready yet."}

    # Fetch associated data
    res_flights = await db.execute(select(Flight).where(Flight.trip_id == trip_id))
    res_hotels = await db.execute(select(Hotel).where(Hotel.trip_id == trip_id))
    res_acts = await db.execute(select(Activity).where(Activity.trip_id == trip_id))
    res_rests = await db.execute(select(Restaurant).where(Restaurant.trip_id == trip_id))
    res_costs = await db.execute(select(CostSummary).where(CostSummary.trip_id == trip_id))

    flights = res_flights.scalars().all()
    hotels = res_hotels.scalars().all()
    activities = res_acts.scalars().all()
    restaurants = res_rests.scalars().all()
    cost_summary = res_costs.scalar_one_or_none()

    # Construct compiled schema
    itinerary_dict = {
        "destination": trip.destination,
        "departure_date": str(trip.start_date),
        "duration_days": trip.duration_days,
        "budget_usd": float(trip.budget_usd),
        "status": trip.status,
        "flight_options": [
            {
                "airline": f.airline,
                "origin_iata": f.origin_code,
                "destination_iata": f.destination_code,
                "price_usd": float(f.price_usd)
            } for f in flights
        ],
        "hotel_options": [
            {
                "name": h.name,
                "address": h.address,
                "price_per_night_usd": float(h.price_per_night_usd),
                "star_rating": h.rating
            } for h in hotels
        ],
        "curated_activities": [
            {
                "name": act.title,
                "category": act.category,
                "description": act.description,
                "cost_usd": float(act.cost_usd)
            } for act in activities
        ],
        "curated_restaurants": [
            {
                "name": r.name,
                "cuisine": r.cuisine,
                "address": r.address,
                "cost_per_person_usd": float(r.cost_per_person_usd)
            } for r in restaurants
        ],
        "cost_summary": {
            "flights_usd": float(cost_summary.flights_usd),
            "hotels_usd": float(cost_summary.hotels_usd),
            "activities_usd": float(cost_summary.activities_usd),
            "food_usd": float(cost_summary.food_usd),
            "total_usd": float(cost_summary.total_usd),
            "budget_remaining_usd": float(cost_summary.budget_remaining_usd)
        } if cost_summary else {}
    }

    # 3. Store in Redis L2 Cache
    await cache.set_itinerary(str(trip_id), itinerary_dict)
    await cache.close()

    return itinerary_dict


@router.put("/trips/{trip_id}", response_model=TripPlanResponse)
async def replan_trip(
    trip_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    trip: Trip = Depends(require_trip_ownership),
    db: AsyncSession = Depends(get_db)
):
    """Clears old itinerary records and triggers the background re-planning task."""
    # Reject with 409 conflict if a planning job is actively running
    cache = TripCache()
    cached_status = await cache.get_planning_status(str(trip_id))
    
    if cached_status == "planning" or trip.status == "planning":
        await cache.close()
        raise ConflictError("Cannot re-plan trip: planning is currently in-progress.")

    # 1. Clear old data from relational tables
    await db.execute(delete(Flight).where(Flight.trip_id == trip_id))
    await db.execute(delete(Hotel).where(Hotel.trip_id == trip_id))
    await db.execute(delete(Activity).where(Activity.trip_id == trip_id))
    await db.execute(delete(Restaurant).where(Restaurant.trip_id == trip_id))
    await db.execute(delete(CostSummary).where(CostSummary.trip_id == trip_id))

    # 2. Reset trip status to planning
    trip.status = "planning"
    trip.completed_at = None
    await db.commit()

    # 3. Set Redis planning state
    await cache.set_planning_status(str(trip_id), "planning")
    await cache.close()

    # 4. Dispatch Celery task
    orchestrate_travel_plan.delay(
        str(trip_id),
        trip.destination,
        "Chicago",  # Default origin
        str(trip.start_date),
        str(trip.start_date + timedelta(days=trip.duration_days)),
        [],  # Empty defaults for replan inputs (loaded from db in real setups)
        [],
        trip.travel_style,
        []
    )

    return TripPlanResponse(trip_id=trip_id, status="planning")


# ==========================================
# ===== 3. HEALTH PROBE ENDPOINTS =====
# ==========================================

@router.get("/health/live", status_code=status.HTTP_200_OK)
async def liveness_probe():
    """Liveness probe returning success to confirm server is up."""
    return {"status": "alive"}


@router.get("/health/ready", status_code=status.HTTP_200_OK)
async def readiness_probe(db: AsyncSession = Depends(get_db)):
    """Readiness probe connecting to PostgreSQL and Redis to assert app health."""
    try:
        # Check PostgreSQL
        await db.execute(select(1))
        
        # Check Redis
        cache = TripCache()
        await cache.client.ping()
        await cache.close()
        
        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_AVAILABLE,
            detail=f"Database or Redis is offline: {str(e)}"
        )
