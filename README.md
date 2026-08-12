# API Endpoints under /api/v1

All endpoints are registered via `app.include_router(router, prefix="/api/v1")` in `src/api/app.py`.

## Authentication

- `POST /api/v1/auth/register`
  - Request body: `UserCreateRequest`
  - Response: `{"message": str, "user_id": str}` (HTTP 201)

- `POST /api/v1/auth/token`
  - Request: `OAuth2PasswordRequestForm` (form data: username, password)
  - Response model: `TokenResponse`

## Trip Planning

- `POST /api/v1/plan`
  - Request body: `TripPlanRequest`
  - Response model: `TripPlanResponse` (HTTP 202)
  - Requires authenticated user

- `GET /api/v1/status/{trip_id}`
  - Path param: `trip_id` (uuid.UUID)
  - Response model: `TripStatusResponse`
  - Requires authenticated user

- `GET /api/v1/trips`
  - Response: list of objects with keys `trip_id`, `destination`, `start_date`, `duration_days`, `budget_usd`, `status`, `created_at`
  - Requires authenticated user

- `GET /api/v1/trips/{trip_id}`
  - Path param: `trip_id` (uuid.UUID)
  - Response: itinerary dict (with keys `destination`, `departure_date`, `duration_days`, `budget_usd`, `status`, `flight_options`, `hotel_options`, `curated_activities`, `curated_restaurants`, `cost_summary`) or `{"trip_id": ..., "status": ..., "message": ...}`
  - Requires trip ownership via `require_trip_ownership`

- `PUT /api/v1/trips/{trip_id}`
  - Path param: `trip_id` (uuid.UUID)
  - Response model: `TripPlanResponse`
  - Requires authenticated user and trip ownership

## Health

- `GET /api/v1/health/live`
  - Response: `{"status": "alive"}` (HTTP 200)

- `GET /api/v1/health/ready`
  - Response: `{"status": "ready"}` (HTTP 200) or HTTP 503 on failure
  - Depends on DB and Redis connectivity