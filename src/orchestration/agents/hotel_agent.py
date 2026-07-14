import json
from datetime import datetime
import httpx
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from src.orchestration.agents.base import get_llm

SYSTEM_PROMPT = """You are an expert travel accommodations specialist.
Your task is to analyze a list of local hotels and guest houses (fetched from OpenStreetMap map data) and recommend the best lodging options matching the traveler's preferences.

Since OpenStreetMap does not contain live pricing, you must:
1. Estimate a realistic "price_per_night_usd" (price per night in USD) for each hotel based on its brand, name, and style (e.g. budget capsule, standard motel, or luxury resort).
2. Calculate the "total_cost_usd" strictly as: price_per_night_usd * {num_nights} nights.
3. Categorize each hotel into a tier: "budget", "mid-range", or "luxury".

You must output your response in raw JSON format matching this exact structure:
[
  {{
    "name": "Hotel Name",
    "address": "Street Address, City, State/Country. Resolve or estimate a clean street address using the raw address metadata and location context.",
    "star_rating": 4.5,
    "price_per_night_usd": 150,
    "total_cost_usd": 1050,
    "latitude": 34.1623,
    "longitude": -94.6934,
    "tier": "budget",
    "why_recommended": "A brief explanation of why this matches their specific travel style (e.g. budget-friendly cabin, scenic forest views, luxury downtown location)."
  }}
]

Rules:
1. Select up to 3 recommended hotels from the options provided. If the options list is empty, use your internal geographical knowledge of the city to generate 3 realistic options.
2. Calculate "total_cost_usd" strictly using: price_per_night_usd * {num_nights}.
3. Output ONLY the raw JSON array. Do not write conversational prefaces or conclusions. Do not wrap the JSON in markdown code blocks (like ```json). Just start with [ and end with ].
"""

def clean_json_string(text: str) -> str:
    """
    Finds the first opening bracket/brace and last closing bracket/brace
    in the text and extracts only the JSON string between them.
    This discards any conversational text written before or after the JSON.
    """
    text = text.strip()
    
    first_bracket = text.find('[')
    first_brace = text.find('{')
    
    start_idx = -1
    end_char = ""
    
    if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
        start_idx = first_bracket
        end_char = ']'
    elif first_brace != -1:
        start_idx = first_brace
        end_char = '}'
        
    if start_idx == -1:
        return text
        
    end_idx = text.rfind(end_char)
    if end_idx == -1 or end_idx < start_idx:
        return text
        
    return text[start_idx : end_idx + 1]

@tool
async def get_hotels(location: str, check_in: str, check_out: str, preferences: list[str]) -> str:
    """
    Search for hotels, cabins, or lodging options near the destination.
    Takes dates and budget/style preferences, and returns a curated JSON string of suggestions.
    """
    try:
        # 1. Calculate the number of nights
        d1 = datetime.strptime(check_in.strip(), "%Y-%m-%d")
        d2 = datetime.strptime(check_out.strip(), "%Y-%m-%d")
        num_nights = (d2 - d1).days
        if num_nights <= 0:
            num_nights = 1  # Minimum fallback

        # 2. Resolve coordinates using robust geocoder
        parts = [p.strip() for p in location.split(",")]
        search_name = parts[0]
        
        async with httpx.AsyncClient() as client:
            geocode_url = "https://geocoding-api.open-meteo.com/v1/search"
            geocode_response = await client.get(
                geocode_url, 
                params={"name": search_name, "count": 10},
                timeout=10.0
            )
            geocode_response.raise_for_status()
            geocode_data = geocode_response.json()
            
            results = geocode_data.get("results")
            if not results:
                return json.dumps({"error": f"Could not geocode location: '{location}'"})
                
            resolved_match = results[0]
            if len(parts) > 1:
                context = parts[1].lower()
                for match in results:
                    admin1 = match.get("admin1", "").lower()
                    country = match.get("country", "").lower()
                    country_code = match.get("country_code", "").lower()
                    if context in admin1 or context in country or context == country_code:
                        resolved_match = match
                        break
                        
            lat = resolved_match["latitude"]
            lon = resolved_match["longitude"]

            # 3. Query OpenStreetMap Overpass API for tourism/accommodation nodes within 1.5km
            overpass_url = "https://lz4.overpass-api.de/api/interpreter"
            overpass_query = f"""[out:json];
            (
              node["tourism"="hotel"](around:1500, {lat}, {lon});
              node["tourism"="motel"](around:1500, {lat}, {lon});
              node["tourism"="guest_house"](around:1500, {lat}, {lon});
              node["tourism"="hostel"](around:1500, {lat}, {lon});
            );
            out body 12;"""
            
            headers = {
                "User-Agent": "MultiAgentTravelPlanner/1.0 (contact@example.com)"
            }
            
            overpass_mirrors = [
                "https://lz4.overpass-api.de/api/interpreter",
                "https://overpass.kumi.systems/api/interpreter",
                "https://overpass.osm.ch/api/interpreter"
            ]
            
            osm_data = None
            last_err = None
            for mirror in overpass_mirrors:
                try:
                    response = await client.post(mirror, data={"data": overpass_query}, headers=headers, timeout=10.0)
                    response.raise_for_status()
                    osm_data = response.json()
                    break  # Success, exit loop
                except Exception as e:
                    last_err = e
                    continue
            
            if not osm_data:
                raise Exception(f"All Overpass API mirrors failed. Last error: {str(last_err)}")
                
            elements = osm_data.get("elements", [])

            # 4. Parse OSM hotels
            raw_hotels = []
            for el in elements:
                tags = el.get("tags", {})
                name = tags.get("name")
                if not name:
                    continue  # Skip unnamed nodes
                
                addr_parts = []
                if "addr:housenumber" in tags:
                    addr_parts.append(tags["addr:housenumber"])
                if "addr:street" in tags:
                    addr_parts.append(tags["addr:street"])
                if "addr:suburb" in tags:
                    addr_parts.append(tags["addr:suburb"])
                if "addr:city" in tags:
                    addr_parts.append(tags["addr:city"])
                raw_address = ", ".join(addr_parts) if addr_parts else "Address tags unavailable"

                raw_hotels.append({
                    "name": name,
                    "raw_address": raw_address,
                    "latitude": el.get("lat"),
                    "longitude": el.get("lon")
                })

            # 5. Initialize LLM and Prompt
            llm = get_llm()
            prompt = ChatPromptTemplate.from_messages([
                ("system", SYSTEM_PROMPT),
                ("human", (
                    "Location: {location}\n"
                    "Check-in Date: {check_in}\n"
                    "Check-out Date: {check_out}\n"
                    "Nights: {num_nights}\n"
                    "Traveler Preferences: {preferences}\n"
                    "OSM Hotels Found:\n{hotels_json}\n"
                ))
            ])
            
            chain = prompt | llm
            response = await chain.ainvoke({
                "location": location,
                "check_in": check_in,
                "check_out": check_out,
                "num_nights": num_nights,
                "preferences": ", ".join(preferences),
                "hotels_json": json.dumps(raw_hotels, indent=2)
            })
            
            content = getattr(response, "content", str(response))
            cleaned_content = clean_json_string(content)
            
            # Verify valid JSON
            json.loads(cleaned_content)
            return cleaned_content
        
    except Exception as e:
        return json.dumps({"error": f"Failed to generate hotel suggestions: {str(e)}"})


# ===== STANDALONE TEST RUNNER =====
if __name__ == "__main__":
    import asyncio

    async def test_agent():
        destination = "Broken Bow, Oklahoma"
        preferences = ["nature", "luxury", "cabin"]
        check_in = "2026-07-20"
        check_out = "2026-07-27"
        
        print(f"Calling get_hotels tool for: {destination}...")
        print(f"Check-in: {check_in} | Check-out: {check_out}")
        print(f"Preferences: {preferences}\n")
        
        result_json = await get_hotels.ainvoke({
            "location": destination,
            "check_in": check_in,
            "check_out": check_out,
            "preferences": preferences
        })
        
        parsed_result = json.loads(result_json)
        print("Curated Hotels Response:")
        print(json.dumps(parsed_result, indent=2))

    asyncio.run(test_agent())
