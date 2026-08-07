import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    Float,
    Boolean,
    DateTime,
    Date,
    Time,
    ForeignKey,
    Text,
    func,
    Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from geoalchemy2 import Geography
from src.db.session import Base


# ===== 1. USERS MODEL =====
class User(Base):
    """Registered user account with credentials and their planned trips."""
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    trips = relationship("Trip", back_populates="user", cascade="all, delete-orphan")


# ===== 2. TRIPS MODEL =====
class Trip(Base):
    """A single travel plan request and its planning status, linked to a user and all its itinerary components."""
    __tablename__ = "trips"

    trip_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    destination = Column(String(255), nullable=False)
    start_date = Column(Date, nullable=False)
    duration_days = Column(Integer, nullable=False)
    budget_usd = Column(Numeric(10, 2), nullable=False)
    travel_style = Column(String(50))
    party_size = Column(Integer, default=1)
    status = Column(String(50), default="planning", index=True)
    idempotency_key = Column(String(255))
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="trips")
    flights = relationship("Flight", back_populates="trip", cascade="all, delete-orphan")
    hotels = relationship("Hotel", back_populates="trip", cascade="all, delete-orphan")
    activities = relationship("Activity", back_populates="trip", cascade="all, delete-orphan")
    restaurants = relationship("Restaurant", back_populates="trip", cascade="all, delete-orphan")
    agent_executions = relationship("AgentExecution", back_populates="trip", cascade="all, delete-orphan")
    cost_summaries = relationship("CostSummary", back_populates="trip", cascade="all, delete-orphan")

    __table_args__ = (
        # Partial unique index for idempotency keys per user
        Index(
            "idx_trips_user_idempotency",
            user_id,
            idempotency_key,
            unique=True,
            postgresql_where=idempotency_key.isnot(None)
        ),
    )


# ===== 3. FLIGHTS MODEL =====
class Flight(Base):
    """A flight option recommended for a trip."""
    __tablename__ = "flights"

    flight_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id = Column(UUID(as_uuid=True), ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False, index=True)
    airline = Column(String(100))
    departure_time = Column(DateTime)
    arrival_time = Column(DateTime)
    origin_code = Column(String(3))
    destination_code = Column(String(3))
    price_usd = Column(Numeric(10, 2))
    duration_hours = Column(Float)
    stops = Column(Integer)
    booking_url = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    trip = relationship("Trip", back_populates="flights")


# ===== 4. HOTELS MODEL =====
class Hotel(Base):
    """A hotel or lodging option recommended for a trip."""
    __tablename__ = "hotels"

    hotel_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id = Column(UUID(as_uuid=True), ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255))
    address = Column(Text)
    # PostGIS point type geography (Longitude, Latitude)
    location = Column(Geography(geometry_type='POINT', srid=4326), index=True)
    check_in_date = Column(Date)
    check_out_date = Column(Date)
    price_per_night_usd = Column(Numeric(10, 2))
    rating = Column(Float)
    amenities = Column(JSONB)
    booking_url = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    trip = relationship("Trip", back_populates="hotels")


# ===== 5. ACTIVITIES MODEL =====
class Activity(Base):
    """A curated activity or sightseeing item recommended for a trip."""
    __tablename__ = "activities"

    activity_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id = Column(UUID(as_uuid=True), ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False, index=True)
    activity_date = Column(Date, nullable=False, index=True)
    time_slot = Column(String(50))
    title = Column(String(255))
    description = Column(Text)
    location_name = Column(String(255))
    # PostGIS point type geography (Longitude, Latitude)
    location = Column(Geography(geometry_type='POINT', srid=4326), index=True)
    start_time = Column(Time)
    end_time = Column(Time)
    cost_usd = Column(Numeric(10, 2))
    category = Column(String(100))
    url = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    trip = relationship("Trip", back_populates="activities")


# ===== 6. RESTAURANTS MODEL =====
class Restaurant(Base):
    """A curated restaurant or dining option recommended for a trip."""
    __tablename__ = "restaurants"

    restaurant_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id = Column(UUID(as_uuid=True), ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False, index=True)
    meal_date = Column(Date)
    meal_type = Column(String(50))
    name = Column(String(255))
    cuisine = Column(String(100))
    address = Column(Text)
    # PostGIS point type geography (Longitude, Latitude)
    location = Column(Geography(geometry_type='POINT', srid=4326))
    rating = Column(Float)
    price_tier = Column(Integer)
    dietary_options = Column(JSONB)
    cost_per_person_usd = Column(Numeric(10, 2))
    reservations_required = Column(Boolean)
    url = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    trip = relationship("Trip", back_populates="restaurants")


# ===== 7. AGENT EXECUTION LOGS MODEL =====
class AgentExecution(Base):
    """Execution log for a single specialist agent run within a trip's planning workflow."""
    __tablename__ = "agent_executions"

    execution_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id = Column(UUID(as_uuid=True), ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False, index=True)
    agent_name = Column(String(100))
    status = Column(String(50))
    execution_time_seconds = Column(Float)
    llm_tokens_used = Column(Integer)
    llm_cost_usd = Column(Numeric(10, 4))
    result = Column(JSONB)
    error_message = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    trip = relationship("Trip", back_populates="agent_executions")


# ===== 8. COST SUMMARIES MODEL =====
class CostSummary(Base):
    """Aggregated cost breakdown and budget utilization for a trip."""
    __tablename__ = "cost_summaries"

    summary_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id = Column(UUID(as_uuid=True), ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False, index=True)
    flights_usd = Column(Numeric(10, 2))
    hotels_usd = Column(Numeric(10, 2))
    activities_usd = Column(Numeric(10, 2))
    food_usd = Column(Numeric(10, 2))
    misc_usd = Column(Numeric(10, 2))
    total_usd = Column(Numeric(10, 2))
    budget_remaining_usd = Column(Numeric(10, 2))
    budget_utilization_pct = Column(Float)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    trip = relationship("Trip", back_populates="cost_summaries")
