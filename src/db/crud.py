import uuid
from datetime import datetime, date, time
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import User, Trip, Flight, Hotel, Activity, Restaurant, CostSummary, AgentExecution


# ===== USER CRUD =====
async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    stmt = select(User).where(User.email == email)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
    stmt = select(User).where(User.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_user(session: AsyncSession, email: str, password_hash: str) -> User:
    new_user = User(email=email, password_hash=password_hash)
    session.add(new_user)
    await session.flush()
    return new_user


# ===== TRIP CRUD =====
async def get_trip(session: AsyncSession, trip_id: uuid.UUID) -> Optional[Trip]:
    stmt = select(Trip).where(Trip.trip_id == trip_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_trips_by_user(session: AsyncSession, user_id: uuid.UUID) -> List[Trip]:
    stmt = select(Trip).where(Trip.user_id == user_id).order_by(Trip.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_trip_status(session: AsyncSession, trip_id: uuid.UUID, status: str, completed: bool = False) -> None:
    update_data = {"status": status}
    if completed:
        update_data["completed_at"] = datetime.now()
    
    stmt = update(Trip).where(Trip.trip_id == trip_id).values(**update_data)
    await session.execute(stmt)


async def create_trip(
    session: AsyncSession,
    user_id: uuid.UUID,
    destination: str,
    start_date: date,
    duration_days: int,
    budget_usd: float,
    travel_style: Optional[str] = None,
    party_size: int = 1,
    idempotency_key: Optional[str] = None
) -> Trip:
    # 1. Enforce Idempotency constraint: Check if this user already submitted this key
    if idempotency_key:
        stmt = select(Trip).where(Trip.user_id == user_id, Trip.idempotency_key == idempotency_key)
        result = await session.execute(stmt)
        existing_trip = result.scalar_one_or_none()
        if existing_trip:
            print(f"DEBUG: Duplicate request detected for idempotency key '{idempotency_key}'. Returning existing trip.")
            return existing_trip

    # 2. Insert new trip record
    new_trip = Trip(
        user_id=user_id,
        destination=destination,
        start_date=start_date,
        duration_days=duration_days,
        budget_usd=Decimal(str(budget_usd)),
        travel_style=travel_style,
        party_size=party_size,
        status="planning",
        idempotency_key=idempotency_key
    )
    session.add(new_trip)
    await session.flush()
    return new_trip


# ===== ITINERARY INTEGRATION =====
async def save_itinerary_details(session: AsyncSession, trip_id: uuid.UUID, compiled: Dict[str, Any]) -> None:
    """
    Saves all details from a compiled itinerary (flights, hotels, activities, restaurants, and cost summary)
    into the database, and marks the trip status as 'completed'.
    """
    
    # Check for agent execution errors in compiled itinerary segments
    for key in ["flight_options", "hotel_options", "curated_activities", "curated_restaurants"]:
        val = compiled.get(key)
        if isinstance(val, dict) and "error" in val:
            raise ValueError(f"Agent execution error in {key}: {val['error']}")

    # 1. Insert Flights
    flight_options = compiled.get("flight_options", {})
    flights_list = flight_options.get("flights", []) if isinstance(flight_options, dict) else []
    total_flight_cost = Decimal("0.00")
    
    for f in flights_list:
        price = Decimal(str(f.get("price_usd", 0.0)))
        
        # Estimate flight cost using the best value flight option
        if f.get("type") == "best_value":
            total_flight_cost = price
                
        new_flight = Flight(
            trip_id=trip_id,
            airline=f.get("airline"),
            origin_code=flight_options.get("origin_iata"),
            destination_code=flight_options.get("destination_iata"),
            price_usd=price,
            stops=f.get("stops", 0),
            booking_url=f.get("booking_url", "")
        )
        session.add(new_flight)

    # 2. Insert Hotels
    hotel_options = compiled.get("hotel_options", [])
    total_hotel_cost = Decimal("0.00")
    
    for h in hotel_options:
        price_night = Decimal(str(h.get("price_per_night_usd", 0.0)))
        total_cost = Decimal(str(h.get("total_cost_usd", 0.0)))
        
        # Set total hotel cost to the first option in the list
        if total_hotel_cost == Decimal("0.00"):
            total_hotel_cost = total_cost

        # GeoAlchemy POINT WKT format: 'POINT(longitude latitude)'
        lat, lon = h.get("latitude"), h.get("longitude")
        location_geom = f"POINT({lon} {lat})" if lat is not None and lon is not None else None

        new_hotel = Hotel(
            trip_id=trip_id,
            name=h.get("name"),
            address=h.get("address"),
            location=location_geom,
            price_per_night_usd=price_night,
            rating=float(h.get("star_rating", 0.0)),
            amenities=h.get("amenities", {}),
            booking_url=h.get("booking_url", "")
        )
        session.add(new_hotel)

    # 3. Insert Activities
    activities_list = compiled.get("curated_activities", [])
    total_activity_cost = Decimal("0.00")
    
    for act in activities_list:
        cost = Decimal(str(act.get("cost_usd", 0.0)))
        total_activity_cost += cost
        
        lat, lon = act.get("latitude"), act.get("longitude")
        location_geom = f"POINT({lon} {lat})" if lat is not None and lon is not None else None

        new_activity = Activity(
            trip_id=trip_id,
            activity_date=datetime.strptime(compiled.get("departure_date"), "%Y-%m-%d").date(),
            title=act.get("name"),
            description=act.get("description"),
            location_name=act.get("name"),
            location=location_geom,
            cost_usd=cost,
            category=act.get("category", "")
        )
        session.add(new_activity)

    # 4. Insert Restaurants
    restaurants_list = compiled.get("curated_restaurants", [])
    total_food_cost = Decimal("0.00")
    
    for r in restaurants_list:
        cost = Decimal(str(r.get("cost_per_person_usd", 15.0)))
        total_food_cost += cost
        
        lat, lon = r.get("latitude"), r.get("longitude")
        location_geom = f"POINT({lon} {lat})" if lat is not None and lon is not None else None

        new_restaurant = Restaurant(
            trip_id=trip_id,
            name=r.get("name"),
            cuisine=r.get("cuisine"),
            address=r.get("address"),
            location=location_geom,
            cost_per_person_usd=cost
        )
        session.add(new_restaurant)

    # 5. Calculate Cost Summary
    trip_record = await get_trip(session, trip_id)
    budget = trip_record.budget_usd if trip_record else Decimal("2000.00")
    
    total_usd = total_flight_cost + total_hotel_cost + total_activity_cost + total_food_cost
    budget_remaining = budget - total_usd
    utilization_pct = float((total_usd / budget) * 100) if budget > 0 else 0.0

    new_summary = CostSummary(
        trip_id=trip_id,
        flights_usd=total_flight_cost,
        hotels_usd=total_hotel_cost,
        activities_usd=total_activity_cost,
        food_usd=total_food_cost,
        misc_usd=Decimal("0.00"),
        total_usd=total_usd,
        budget_remaining_usd=budget_remaining,
        budget_utilization_pct=utilization_pct
    )
    session.add(new_summary)

    # 6. Update Trip Status to completed
    await update_trip_status(session, trip_id, status="completed", completed=True)

    # 7. Write calculated costs into compiled dict in-place so Celery L2 cache has it
    compiled["cost_summary"] = {
        "flights_usd": float(total_flight_cost),
        "hotels_usd": float(total_hotel_cost),
        "activities_usd": float(total_activity_cost),
        "food_usd": float(total_food_cost),
        "total_usd": float(total_usd),
        "budget_remaining_usd": float(budget_remaining)
    }


# ===== AGENT LOGGING =====
async def log_agent_execution(
    session: AsyncSession,
    trip_id: uuid.UUID,
    agent_name: str,
    status: str,
    execution_time: float,
    tokens: int = 0,
    cost: float = 0.0,
    result_json: Optional[Dict[str, Any]] = None,
    error_msg: Optional[str] = None
) -> AgentExecution:
    new_log = AgentExecution(
        trip_id=trip_id,
        agent_name=agent_name,
        status=status,
        execution_time_seconds=execution_time,
        llm_tokens_used=tokens,
        llm_cost_usd=Decimal(str(cost)),
        result=result_json,
        error_message=error_msg
    )
    session.add(new_log)
    await session.flush()
    return new_log
