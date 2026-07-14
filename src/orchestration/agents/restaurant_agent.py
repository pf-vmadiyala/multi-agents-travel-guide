import json
import httpx
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from src.orchestration.agents.base import get_llm

SYSTEM_PROMPT = """You are an expert travel culinary specialist.
Your task is to analyze a list of nearby restaurants and cafes (including their coordinates and any raw address tags) and curate a personalized list of dining recommendations that match the traveler's food preferences.

You must output your response in raw JSON format matching this exact structure:
[
  {{
    "name": "Restaurant Name",
    "cuisine": "Cuisine Type (e.g. Sushi, Italian, BBQ)",
    "address": "Cleaned, formatted street address (e.g. 123 Main St, Shinjuku, Tokyo). Resolve or estimate a reasonable street address based on the raw address metadata and location coordinates.",
    "description": "A short, engaging description of what they serve or their vibe.",
    "latitude": 35.6895,
    "longitude": 139.6917,
    "why_recommended": "A brief explanation of why this matches their specific food interests."
  }}
]

Rules:
1. Select up to 5 unique dining options from the list provided.
2. Only select options that match or align well with at least one of the traveler's food preferences/interests.
3. If the raw address tags are sparse or say "Address tags unavailable", use your internal knowledge of the location coordinates and district to estimate a clean, human-readable street address.
4. Output ONLY the raw JSON array. Do not write conversational prefaces or conclusions. Do not wrap the JSON in markdown code blocks (like ```json). Just start with [ and end with ].
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
    
    # Determine if we are extracting an array [...] or object {...}
    if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
        start_idx = first_bracket
        end_char = ']'
    elif first_brace != -1:
        start_idx = first_brace
        end_char = '}'
        
    if start_idx == -1:
        return text  # No brackets/braces found, let json.loads fail naturally
        
    end_idx = text.rfind(end_char)
    if end_idx == -1 or end_idx < start_idx:
        return text
        
    return text[start_idx : end_idx + 1]

@tool
async def get_restaurants(location: str, cuisines: list[str]) -> str:
    """
    Search for restaurants, cafes, and diners near a destination that match
    the traveler's cuisine preferences. Returns a JSON string of curated options.
    """
    try:
        async with httpx.AsyncClient() as client:
            # 1. Resolve location name to coordinates using a robust comma-splitting search
            parts = [p.strip() for p in location.split(",")]
            search_name = parts[0]
            
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
                
            # Filter results using the state/country context if provided
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

            # 2. Query OpenStreetMap's Overpass API for restaurants/cafes within 1.5km (with fallback mirrors)
            overpass_query = f"""[out:json];
            (
              node["amenity"="restaurant"](around:1500, {lat}, {lon});
              node["amenity"="cafe"](around:1500, {lat}, {lon});
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
            
            if not elements:
                return json.dumps([])

            # 3. Parse OSM results and extract addresses
            raw_restaurants = []
            for el in elements:
                tags = el.get("tags", {})
                name = tags.get("name")
                if not name:
                    continue  # Skip unnamed nodes
                
                # Combine standard OSM address tags if present
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

                raw_restaurants.append({
                    "name": name,
                    "cuisine": tags.get("cuisine", "Local Cuisine"),
                    "raw_address": raw_address,
                    "latitude": el.get("lat"),
                    "longitude": el.get("lon")
                })

            # 4. Initialize LLM and prompt to filter and format the recommendations
            llm = get_llm()
            prompt = ChatPromptTemplate.from_messages([
                ("system", SYSTEM_PROMPT),
                ("human", (
                    "Destination: {destination}\n"
                    "Traveler Cuisine Preferences: {cuisines}\n"
                    "Nearby Restaurants Found:\n{restaurants_json}\n"
                ))
            ])
            
            chain = (prompt | llm).with_config({"run_name": "Restaurant_Curator"})
            response = await chain.ainvoke({
                "destination": location,
                "cuisines": ", ".join(cuisines),
                "restaurants_json": json.dumps(raw_restaurants, indent=2)
            })
            
            content = getattr(response, "content", str(response))
            cleaned_content = clean_json_string(content)
            
            # Verify valid JSON list
            json.loads(cleaned_content)
            return cleaned_content
            
    except Exception as e:
        return json.dumps({"error": f"Failed to generate restaurant suggestions: {str(e)}"})


# ===== STANDALONE TEST RUNNER =====
if __name__ == "__main__":
    import asyncio

    async def test_agent():
        # Test interests matching Tokyo
        destination = "Broken Bow, Oklahoma"
        cuisines = ["pizza", "burgers", "coffee", "bbq", "mexican"]
        
        print(f"Calling get_restaurants tool for: {destination}...")
        print(f"Preferences: {cuisines}\n")
        
        # Invoke tool asynchronously using .ainvoke
        result_json = await get_restaurants.ainvoke({
            "location": destination,
            "cuisines": cuisines
        })
        
        parsed_result = json.loads(result_json)
        print("Curated Restaurants Response:")
        print(json.dumps(parsed_result, indent=2))

    asyncio.run(test_agent())
