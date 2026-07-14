import os
import json
import httpx
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from src.orchestration.agents.base import get_llm

SYSTEM_PROMPT = """You are an expert travel aviation specialist.
Your task is to analyze flight search options between the origin and destination and recommend the best options for the traveler.

You must output your response in raw JSON format matching this exact structure:
{{
  "origin_iata": "ORD",
  "destination_iata": "NRT",
  "flights": [
    {{
      "airline": "United Airlines",
      "flight_number": "UA881",
      "departure_time": "12:35",
      "arrival_time": "15:45 (+1)",
      "price_usd": 950,
      "duration": "13h 10m",
      "stops": 0,
      "type": "cheapest", // Must be one of: "cheapest", "fastest", or "best_value"
      "why_recommended": "A brief explanation of why this matches their specific flight preference."
    }}
  ]
}}

Rules:
1. Select exactly 3 recommended flights: one tagged as "cheapest", one as "fastest", and one as "best_value".
2. If the options list is empty or says "No live flights", use your internal knowledge to generate 3 realistic flights for the route.
3. Automatically determine the correct 3-letter IATA airport codes for the origin and destination (e.g. Chicago -> ORD, Tokyo -> NRT/HND) and populate the "origin_iata" and "destination_iata" fields.
4. Output ONLY the raw JSON object. Do not write conversational prefaces or conclusions. Do not wrap the JSON in markdown code blocks (like ```json). Just start with {{ and end with }}.
"""

def clean_json_string(text: str) -> str:
    """
    Finds the first opening brace and last closing brace in the text
    and extracts only the JSON string. Discards any conversational text around it.
    """
    text = text.strip()
    first_brace = text.find('{')
    if first_brace == -1:
        return text
    end_idx = text.rfind('}')
    if end_idx == -1 or end_idx < first_brace:
        return text
    return text[first_brace : end_idx + 1]

@tool
async def get_flights(origin: str, destination: str, departure_date: str, return_date: str, preferences: list[str]) -> str:
    """
    Search for flights between an origin and destination for specific dates.
    Uses Duffel API if configured, otherwise falls back to a realistic LLM generator.
    """
    try:
        duffel_api_key = os.getenv("DUFFEL_API_KEY")
        live_flights_found = []
        
        # 1. Real API Mode: Query Duffel if API key is present
        if duffel_api_key:
            try:
                # We need to resolve IATA codes first using LLM
                llm = get_llm()
                iata_prompt = ChatPromptTemplate.from_template(
                    "Resolve the cities '{origin}' and '{destination}' to their primary international "
                    "airport 3-letter IATA codes. Return a JSON object ONLY: {{\"origin\": \"IATA\", \"destination\": \"IATA\"}}"
                )
                iata_response = await (iata_prompt | llm).ainvoke({})
                iata_content = clean_json_string(getattr(iata_response, "content", str(iata_response)))
                iata_data = json.loads(iata_content)
                origin_iata = iata_data["origin"].upper()
                destination_iata = iata_data["destination"].upper()

                # Call Duffel API
                url = "https://api.duffel.com/air/offer_requests"
                headers = {
                    "Authorization": f"Bearer {duffel_api_key}",
                    "Duffel-Version": "v1",
                    "Content-Type": "application/json"
                }
                payload = {
                    "data": {
                        "slices": [
                            {
                                "origin": origin_iata,
                                "destination": destination_iata,
                                "departure_date": departure_date
                            },
                            {
                                "origin": destination_iata,
                                "destination": origin_iata,
                                "departure_date": return_date
                            }
                        ],
                        "passengers": [{"type": "adult"}],
                        "cabin_class": "economy"
                    }
                }
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, json=payload, headers=headers, timeout=15.0)
                    response.raise_for_status()
                    data = response.json()
                    offers = data.get("data", {}).get("offers", [])
                    
                    # Parse live offers into simple structures
                    for offer in offers[:10]:
                        slices = offer.get("slices", [])
                        total_amount = float(offer.get("total_amount", 0))
                        airline_name = offer.get("owner", {}).get("name", "Unknown Airline")
                        
                        # Calculate total duration and stops
                        total_duration_mins = 0
                        stops = 0
                        flight_num = "Unknown"
                        
                        for s in slices:
                            segments = s.get("segments", [])
                            stops += max(0, len(segments) - 1)
                            for seg in segments:
                                flight_num = f"{seg.get('marketing_carrier', {}).get('iata_code')}{seg.get('marketing_carrier_flight_number')}"
                        
                        live_flights_found.append({
                            "airline": airline_name,
                            "flight_number": flight_num,
                            "price_usd": total_amount,
                            "stops": stops
                        })
            except Exception as e:
                # If Duffel call fails, print warning and fallback to stub mode
                print(f"Warning: Duffel API call failed ({str(e)}). Falling back to Stub Mode.")
                live_flights_found = []

        # 2. Initialize LLM for recommendation curation
        llm = get_llm()
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", (
                "Origin: {origin}\n"
                "Destination: {destination}\n"
                "Departure Date: {departure_date}\n"
                "Return Date: {return_date}\n"
                "Preferences: {preferences}\n"
                "Live Flights Retrieved: \n{live_flights_json}\n"
            ))
        ])
        
        chain = prompt | llm
        response = await chain.ainvoke({
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
            "return_date": return_date,
            "preferences": ", ".join(preferences),
            "live_flights_json": json.dumps(live_flights_found, indent=2) if live_flights_found else "No live flights (use internal knowledge)"
        })
        
        content = getattr(response, "content", str(response))
        cleaned_content = clean_json_string(content)
        
        # Verify valid JSON
        json.loads(cleaned_content)
        return cleaned_content
        
    except Exception as e:
        return json.dumps({"error": f"Failed to generate flight suggestions: {str(e)}"})


# ===== STANDALONE TEST RUNNER =====
if __name__ == "__main__":
    import asyncio

    async def test_agent():
        origin = "Chicago"
        destination = "Tokyo, Japan"
        preferences = ["direct", "economy"]
        departure_date = "2026-07-20"
        return_date = "2026-07-27"
        
        print(f"Calling get_flights tool from: {origin} to {destination}...")
        print(f"Departure: {departure_date} | Return: {return_date}")
        print(f"Preferences: {preferences}\n")
        
        result_json = await get_flights.ainvoke({
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
            "return_date": return_date,
            "preferences": preferences
        })
        
        parsed_result = json.loads(result_json)
        print("Curated Flights Response:")
        print(json.dumps(parsed_result, indent=2))

    asyncio.run(test_agent())
