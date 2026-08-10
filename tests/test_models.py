import pytest
from datetime import date, timedelta
from src.api.models import TripPlanRequest

def test_validate_dates_raises_valueerror_on_none_dates():
    """Reproduce crash: None dates reach validator and raise TypeError instead of ValueError."""
    data = {
        "destination": "Broken Bow, Oklahoma",
        "origin": "Chicago",
        "departure_date": None,
        "return_date": None,
        "budget_usd": 1000.0,
        "interests": [],
        "cuisines": [],
        "flight_preferences": [],
    }
    obj = TripPlanRequest.model_construct(**data)
    with pytest.raises(ValueError):
        obj.validate_dates()
