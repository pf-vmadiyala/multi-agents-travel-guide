import json
from typing import TypedDict, List, Any
from datetime import datetime, timedelta
from langgraph.graph import StateGraph, START, END

# Import agent functions
from src.orchestration.agents.weather_agent import get_weather_forecast
from src.orchestration.agents.safety_agent import generate_safety_report
from src.orchestration.agents.flight_agent import get_flights
from src.orchestration.agents.hotel_agent import get_hotels
from src.orchestration.agents.activity_agent import get_activities
from src.orchestration.agents.restaurant_agent import get_restaurants
from src.orchestration.agents.packing_agent import generate_packing_list

from src.utils.metrics import agent_success_total, agent_failure_total

def record_agent_metric(agent_name: str, result: Any):
    """Increments agent execution success or failure counters."""
    if isinstance(result, dict) and "error" in result:
        agent_failure_total.labels(agent_name=agent_name).inc()
    else:
        agent_success_total.labels(agent_name=agent_name).inc()


# ===== 1. DEFINE WORKFLOW STATE =====
class ItineraryState(TypedDict):
    # Inputs
    destination: str
    origin: str
    departure_date: str
    return_date: str
    interests: List[str]
    cuisines: List[str]
    travel_style: List[str]
    flight_preferences: List[str]

    # Calculated Trip Dates
    dates: List[str]

    # Outputs populated by agents
    weather: Any
    safety: Any
    flights: Any
    hotels: Any
    activities: Any
    restaurants: Any
    packing_list: Any

    # Final Combined Output
    compiled_itinerary: Any


# ===== HELPER: GENERATE DATES IN RANGE =====
def get_dates_in_range(start_str: str, end_str: str) -> List[str]:
    try:
        start = datetime.strptime(start_str.strip(), "%Y-%m-%d")
        end = datetime.strptime(end_str.strip(), "%Y-%m-%d")
        delta = (end - start).days
        return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(delta + 1)]
    except Exception:
        return [start_str, end_str]


# ===== 2. DEFINE NODE FUNCTIONS =====
async def weather_node(state: ItineraryState) -> dict:
    print("-> Running Weather Agent...")
    dates = get_dates_in_range(state["departure_date"], state["return_date"])
    # Open-Meteo limit is 14 days
    forecast_raw = await get_weather_forecast.ainvoke({
        "location": state["destination"],
        "dates": dates[:14]
    })
    try:
        forecast = json.loads(forecast_raw)
    except Exception:
        forecast = {"error": "Failed to parse weather forecast JSON", "raw": forecast_raw}
    
    record_agent_metric("weather", forecast)
    return {"weather": forecast, "dates": dates}


async def safety_node(state: ItineraryState) -> dict:
    print("-> Running Safety Agent...")
    report_raw = await generate_safety_report(state["destination"])
    try:
        report = json.loads(report_raw)
    except Exception:
        report = {"error": "Failed to parse safety report JSON", "raw": report_raw}
    
    record_agent_metric("safety", report)
    return {"safety": report}


async def flights_node(state: ItineraryState) -> dict:
    print("-> Running Flight Agent...")
    flights_raw = await get_flights.ainvoke({
        "origin": state["origin"],
        "destination": state["destination"],
        "departure_date": state["departure_date"],
        "return_date": state["return_date"],
        "preferences": state.get("flight_preferences", ["economy"])
    })
    try:
        flights = json.loads(flights_raw)
    except Exception:
        flights = {"error": "Failed to parse flights JSON", "raw": flights_raw}
    
    record_agent_metric("flights", flights)
    return {"flights": flights}


async def hotels_node(state: ItineraryState) -> dict:
    print("-> Running Hotel Agent...")
    hotels_raw = await get_hotels.ainvoke({
        "location": state["destination"],
        "check_in": state["departure_date"],
        "check_out": state["return_date"],
        "preferences": state.get("travel_style", ["mid-range"])
    })
    try:
        hotels = json.loads(hotels_raw)
    except Exception:
        hotels = {"error": "Failed to parse hotels JSON", "raw": hotels_raw}
    
    record_agent_metric("hotels", hotels)
    return {"hotels": hotels}


async def activities_node(state: ItineraryState) -> dict:
    print("-> Running Activity Agent...")
    activities_raw = await get_activities.ainvoke({
        "location": state["destination"],
        "interests": state["interests"]
    })
    try:
        activities = json.loads(activities_raw)
    except Exception:
        activities = {"error": "Failed to parse activities JSON", "raw": activities_raw}
    
    record_agent_metric("activities", activities)
    return {"activities": activities}


async def restaurants_node(state: ItineraryState) -> dict:
    print("-> Running Restaurant Agent...")
    restaurants_raw = await get_restaurants.ainvoke({
        "location": state["destination"],
        "cuisines": state["cuisines"]
    })
    try:
        restaurants = json.loads(restaurants_raw)
    except Exception:
        restaurants = {"error": "Failed to parse restaurants JSON", "raw": restaurants_raw}
    
    record_agent_metric("restaurants", restaurants)
    return {"restaurants": restaurants}


async def packing_node(state: ItineraryState) -> dict:
    print("-> Running Packing Agent (Dependent on Weather)...")
    packing_raw = await generate_packing_list(
        destination=state["destination"],
        interests=state["interests"],
        weather_forecast_json=json.dumps(state["weather"])
    )
    try:
        packing = json.loads(packing_raw)
    except Exception:
        packing = {"error": "Failed to parse packing list JSON", "raw": packing_raw}
    
    record_agent_metric("packing", packing)
    return {"packing_list": packing}


async def compile_itinerary_node(state: ItineraryState) -> dict:
    print("-> Compiling final itinerary...")
    compiled = {
        "destination": state["destination"],
        "origin": state["origin"],
        "departure_date": state["departure_date"],
        "return_date": state["return_date"],
        "weather_forecast": state.get("weather"),
        "safety_advisory": state.get("safety"),
        "flight_options": state.get("flights"),
        "hotel_options": state.get("hotels"),
        "curated_activities": state.get("activities"),
        "curated_restaurants": state.get("restaurants"),
        "packing_list": state.get("packing_list")
    }
    return {"compiled_itinerary": compiled}


# ===== 3. CONSTRUCT LANGGRAPH STATE GRAPH =====
workflow = StateGraph(ItineraryState)

# Add Nodes
workflow.add_node("weather", weather_node)
workflow.add_node("safety", safety_node)
workflow.add_node("flights", flights_node)
workflow.add_node("hotels", hotels_node)
workflow.add_node("activities", activities_node)
workflow.add_node("restaurants", restaurants_node)
workflow.add_node("packing", packing_node)
workflow.add_node("compile", compile_itinerary_node)

# Add Parallel Edges from START
workflow.add_edge(START, "weather")
workflow.add_edge(START, "safety")
workflow.add_edge(START, "flights")
workflow.add_edge(START, "hotels")
workflow.add_edge(START, "activities")
workflow.add_edge(START, "restaurants")

# Weather must lead to Packing
workflow.add_edge("weather", "packing")

# All paths merge into Compile Node
workflow.add_edge("packing", "compile")
workflow.add_edge("safety", "compile")
workflow.add_edge("flights", "compile")
workflow.add_edge("hotels", "compile")
workflow.add_edge("activities", "compile")
workflow.add_edge("restaurants", "compile")

workflow.add_edge("compile", END)

# Compile Graph
travel_planner_app = workflow.compile()


# ===== STANDALONE TEST RUNNER =====
if __name__ == "__main__":
    import asyncio

    async def run_test_planner():
        inputs = {
            "destination": "Broken Bow, Oklahoma",
            "origin": "Chicago",
            "departure_date": "2026-07-20",
            "return_date": "2026-07-27",
            "interests": ["nature", "hiking"],
            "cuisines": ["coffee", "bbq", "burgers"],
            "travel_style": ["luxury", "cabin"],
            "flight_preferences": ["economy"]
        }

        print("=== LAUNCHING TRAVEL PLANNER ORCHESTRATOR ===")
        print(f"Planning trip to: {inputs['destination']} for {inputs['departure_date']} to {inputs['return_date']}\n")

        # Custom config tags and metadata for LangSmith tracing
        config = {
            "run_name": f"TravelPlanner_{inputs['destination'].replace(', ', '_')}",
            "tags": [inputs["destination"], "CLI-Test"],
            "metadata": {
                "destination": inputs["destination"],
                "origin": inputs["origin"],
                "departure_date": inputs["departure_date"],
                "return_date": inputs["return_date"]
            }
        }

        final_state = await travel_planner_app.ainvoke(inputs, config=config)

        print("\n=== COMPILING COMPLETE ITINERARY RESULT ===")
        print(json.dumps(final_state["compiled_itinerary"], indent=2))

    asyncio.run(run_test_planner())
