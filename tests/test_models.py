import pytest
from datetime import date
from src.api.models import TripPlanRequest

def test_validate_dates_raises_valueerror_on_none_departure():
    req = TripPlanRequest.model_construct(
        destination="Broken Bow, Oklahoma",
        origin="Chicago",
        departure_date=None,
        return_date=date.today(),
        budget_usd=1000.0,
        party_size=1,
        interests=[],
        cuisines=[],
        flight_preferences=[],
        travel_style=None,
    )
    with pytest.raises(ValueError):
        req.validate_dates()
