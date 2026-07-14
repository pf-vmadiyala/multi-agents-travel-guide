-- Enable PostGIS extension for geospatial types and operations
CREATE EXTENSION IF NOT EXISTS postgis;

-- ===== TRIGGER FUNCTION FOR AUTO-UPDATING UPDATED_AT =====
CREATE OR REPLACE FUNCTION set_updated_at() 
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ===== USERS TABLE =====
CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TRIGGER users_set_updated_at 
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ===== TRIPS TABLE =====
CREATE TABLE trips (
    trip_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    destination VARCHAR(255) NOT NULL,
    start_date DATE NOT NULL,
    duration_days INT NOT NULL CHECK (duration_days BETWEEN 1 AND 30),
    budget_usd DECIMAL(10, 2) NOT NULL CHECK (budget_usd > 0),
    travel_style VARCHAR(50),
    party_size INT DEFAULT 1,
    status VARCHAR(50) DEFAULT 'planning',
    idempotency_key VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance and idempotency constraint
CREATE INDEX idx_trips_user_id ON trips(user_id);
CREATE INDEX idx_trips_status ON trips(status);
CREATE UNIQUE INDEX idx_trips_user_idempotency ON trips(user_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE TRIGGER trips_set_updated_at 
BEFORE UPDATE ON trips
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ===== FLIGHTS TABLE =====
CREATE TABLE flights (
    flight_id UUID PRIMARY KEY,
    trip_id UUID NOT NULL REFERENCES trips(trip_id) ON DELETE CASCADE,
    airline VARCHAR(100),
    departure_time TIMESTAMP,
    arrival_time TIMESTAMP,
    origin_code VARCHAR(3),
    destination_code VARCHAR(3),
    price_usd DECIMAL(10, 2),
    duration_hours FLOAT,
    stops INT,
    booking_url TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_flights_trip_id ON flights(trip_id);

-- ===== HOTELS TABLE =====
CREATE TABLE hotels (
    hotel_id UUID PRIMARY KEY,
    trip_id UUID NOT NULL REFERENCES trips(trip_id) ON DELETE CASCADE,
    name VARCHAR(255),
    address TEXT,
    location GEOGRAPHY(POINT, 4326),  -- Spatial type for hotels
    check_in_date DATE,
    check_out_date DATE,
    price_per_night_usd DECIMAL(10, 2),
    rating FLOAT,
    amenities JSONB,
    booking_url TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_hotels_trip_id ON hotels(trip_id);
CREATE INDEX idx_hotels_location ON hotels USING GIST(location); -- Geospatial index

-- ===== ACTIVITIES TABLE =====
CREATE TABLE activities (
    activity_id UUID PRIMARY KEY,
    trip_id UUID NOT NULL REFERENCES trips(trip_id) ON DELETE CASCADE,
    activity_date DATE NOT NULL,
    time_slot VARCHAR(50),
    title VARCHAR(255),
    description TEXT,
    location_name VARCHAR(255),
    location GEOGRAPHY(POINT, 4326), -- Spatial type for activities
    start_time TIME,
    end_time TIME,
    cost_usd DECIMAL(10, 2),
    category VARCHAR(100),
    url TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_activities_trip_id ON activities(trip_id);
CREATE INDEX idx_activities_date ON activities(activity_date);
CREATE INDEX idx_activities_location ON activities USING GIST(location); -- Geospatial index

-- ===== RESTAURANTS TABLE =====
CREATE TABLE restaurants (
    restaurant_id UUID PRIMARY KEY,
    trip_id UUID NOT NULL REFERENCES trips(trip_id) ON DELETE CASCADE,
    meal_date DATE,
    meal_type VARCHAR(50),
    name VARCHAR(255),
    cuisine VARCHAR(100),
    address TEXT,
    location GEOGRAPHY(POINT, 4326), -- Spatial type for restaurants
    rating FLOAT,
    price_tier INT,
    dietary_options JSONB,
    cost_per_person_usd DECIMAL(10, 2),
    reservations_required BOOLEAN,
    url TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_restaurants_trip_id ON restaurants(trip_id);

-- ===== AGENT EXECUTION LOG TABLE =====
CREATE TABLE agent_executions (
    execution_id UUID PRIMARY KEY,
    trip_id UUID NOT NULL REFERENCES trips(trip_id) ON DELETE CASCADE,
    agent_name VARCHAR(100),
    status VARCHAR(50),
    execution_time_seconds FLOAT,
    llm_tokens_used INT,
    llm_cost_usd DECIMAL(10, 4),
    result JSONB,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_agent_executions_trip_id ON agent_executions(trip_id);

-- ===== COST TRACKING TABLE =====
CREATE TABLE cost_summaries (
    summary_id UUID PRIMARY KEY,
    trip_id UUID NOT NULL REFERENCES trips(trip_id) ON DELETE CASCADE,
    flights_usd DECIMAL(10, 2),
    hotels_usd DECIMAL(10, 2),
    activities_usd DECIMAL(10, 2),
    food_usd DECIMAL(10, 2),
    misc_usd DECIMAL(10, 2),
    total_usd DECIMAL(10, 2),
    budget_remaining_usd DECIMAL(10, 2),
    budget_utilization_pct FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_cost_summaries_trip_id ON cost_summaries(trip_id);