import uuid
from datetime import date
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, model_validator

# Whitelisted interests allowed in the planner
APPROVED_INTERESTS = {
    "nature", "hiking", "shopping", "food", "culture", 
    "history", "adventure", "relaxation", "museums"
}

# ===== 1. USER AUTH SCHEMAS =====

class UserCreateRequest(BaseModel):
    """Schema for registering a new user."""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters long.")

class TokenResponse(BaseModel):
    """Response containing JWT access token."""
    access_token: str
    token_type: str = "bearer"

# ===== 2. TRIP PLANNING REQUESTS =====

class TripPlanRequest(BaseModel):
    """Schema for requesting a new travel plan."""
    destination: str = Field(..., min_length=2, example="Broken Bow, Oklahoma")
    origin: str = Field(..., min_length=2, example="Chicago")
    departure_date: date
    return_date: date
    budget_usd: float = Field(..., gt=0, description="Total budget in USD must be positive.")
    travel_style: Optional[str] = Field("moderate", description="e.g. luxury, moderate, budget")
    party_size: int = Field(1, ge=1, description="Number of travelers.")
    interests: List[str] = Field(default_factory=list, description="List of user travel interests.")
    cuisines: List[str] = Field(default_factory=list, description="Preferred food cuisines.")
    flight_preferences: List[str] = Field(default_factory=list, description="Cabin class or airline choices.")

    @model_validator(mode="after")
    def validate_dates(self) -> "TripPlanRequest":
        """Validate that departure/return dates are sane and the trip duration doesn't exceed 30 days."""
        # 1. Enforce that departure date is today or in the future
        if self.departure_date < date.today():
            raise ValueError("Departure date cannot be in the past.")
        
        # 2. Enforce return date occurs after departure date
        if self.return_date <= self.departure_date:
            raise ValueError("Return date must occur after the departure date.")
            
        # 3. Limit duration of planning to 30 days max (per Section 8.1 LLD)
        duration_days = (self.return_date - self.departure_date).days
        if duration_days > 30:
            raise ValueError("Trip duration cannot exceed 30 days.")
            
        return self

    @model_validator(mode="after")
    def validate_interests(self) -> "TripPlanRequest":
        """Validate that all requested interests are in the approved whitelist."""
        # Check all interests are inside the approved whitelist
        invalid_interests = [i for i in self.interests if i.lower() not in APPROVED_INTERESTS]
        if invalid_interests:
            raise ValueError(
                f"Invalid interests: {invalid_interests}. Approved categories: {list(APPROVED_INTERESTS)}"
            )
        return self

# ===== 3. STATUS & ITINERARY RESPONSES =====

class TripPlanResponse(BaseModel):
    """Response immediately returned when a trip planning job is queued."""
    trip_id: uuid.UUID
    status: str
    message: str = "Trip planning initiated successfully."

class TripStatusResponse(BaseModel):
    """Response returned when polling status of a trip plan."""
    trip_id: uuid.UUID
    status: str  # planning, completed, failed
