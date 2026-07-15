import json
import httpx
from typing import Any
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from src.orchestration.agents.base import get_llm

SYSTEM_PROMPT = """You are an expert travel activity planner.
Your task is to analyze a list of nearby landmarks and sights (with their Wikipedia summaries and coordinates) and curate a personalized list of activities that match the traveler's interests.

You must output your response in raw JSON format matching this exact structure:
[
  {{
    "name": "Sight Name",
    "category": "Sight Category (e.g. Historic Temple, Nature Park, Art Museum)",
    "description": "A short, engaging description of the sight.",
    "latitude": 35.7147,
    "longitude": 139.7966,
    "matching_interest": "interest_name", // Must match one of the traveler's provided interests
    "why_recommended": "A brief explanation of why this matches their specific interest."
  }}
]

Rules:
1. Select up to 5 unique activities from the list of sights provided.
2. Only select activities that match or align well with at least one of the traveler's provided interests.
3. If none of the sights match any interests, you can suggest 2-3 of the most globally famous landmarks in the list as general must-sees, mapping them to "general".
4. Output ONLY the raw JSON array. Do not write conversational prefaces or conclusions. Do not wrap the JSON in markdown code blocks (like ```json). Just start with [ and end with ].
"""

def clean_json_string(text: Any) -> str:
    """
    Finds the first opening bracket/brace and last closing bracket/brace
    in the text and extracts only the JSON string between them.
    This discards any conversational text written before or after the JSON.
    """
    if isinstance(text, list):
        text = "".join([block.get("text", "") if isinstance(block, dict) else str(block) for block in text])
    elif not isinstance(text, str):
        text = str(text)

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
async def get_activities(location: str, interests: list[str]) -> str:
    """
    Search for travel activities, landmarks, and sightseeing spots near a destination
    that match the traveler's interest categories (e.g., history, nature, shopping).
    Returns a JSON string of curated recommendations.
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

            # 2. Query Wikipedia Geo-Search API for articles near coordinates
            wiki_api_url = "https://en.wikipedia.org/w/api.php"
            headers = {
                "User-Agent": "MultiAgentTravelPlanner/1.0 (contact@example.com)"
            }
            geo_params = {
                "action": "query",
                "list": "geosearch",
                "gscoord": f"{lat}|{lon}",
                "gsradius": 10000,  # 10km radius
                "gslimit": 8,       # Get top 8 results
                "format": "json"
            }
            
            curated_sights = []
            try:
                geo_response = await client.get(wiki_api_url, params=geo_params, headers=headers, timeout=10.0)
                geo_response.raise_for_status()
                geo_data = geo_response.json()
                sights = geo_data.get("query", {}).get("geosearch", [])
                
                if sights:
                    # Extract page IDs to query extracts
                    page_ids = [sight["pageid"] for sight in sights]
                    
                    # 3. Query Wikipedia page summaries (Extracts) for the retrieved pages
                    extract_params = {
                        "action": "query",
                        "prop": "extracts",
                        "exintro": True,
                        "explaintext": True,
                        "pageids": "|".join(str(pid) for pid in page_ids),
                        "format": "json"
                    }
                    extract_response = await client.get(wiki_api_url, params=extract_params, headers=headers, timeout=10.0)
                    extract_response.raise_for_status()
                    extract_data = extract_response.json()
                    pages_dict = extract_data.get("query", {}).get("pages", {})

                    # 4. Merge coordinates, title, and summaries
                    for sight in sights:
                        page_id_str = str(sight["pageid"])
                        summary = pages_dict.get(page_id_str, {}).get("extract", "No description available.")
                        curated_sights.append({
                            "title": sight["title"],
                            "summary": summary[:120] + "...",  # Truncated to save tokens
                            "latitude": sight["lat"],
                            "longitude": sight["lon"],
                        })
            except Exception as wiki_err:
                print(f"Warning: Wikipedia query failed ({str(wiki_err)}). Falling back to LLM internal knowledge.")

            # 5. Initialize LLM and prompt to filter/personalize activities
            llm = get_llm()
            
            if curated_sights:
                system_prompt = SYSTEM_PROMPT
                human_message = (
                    "Destination: {destination}\n"
                    "Traveler Interests: {interests}\n"
                    "Nearby Sight Options:\n{sights_json}\n"
                )
            else:
                system_prompt = (
                    "You are an expert travel activity planner.\n"
                    "Wikipedia data is currently unavailable. You must curate a personalized list of 3-5 famous landmarks, "
                    "sightseeing activities, and sights directly from your own memory/knowledge that match the traveler's interests.\n"
                    "Make sure to guess the coordinates (latitude and longitude) of these locations as accurately as possible.\n\n"
                    "You must output your response in raw JSON format matching this exact structure:\n"
                    "[\n"
                    "  {{\n"
                    "    \"name\": \"Sight Name\",\n"
                    "    \"category\": \"Sight Category (e.g. Historic Temple, Nature Park, Art Museum)\",\n"
                    "    \"description\": \"A short, engaging description of the sight.\",\n"
                    "    \"latitude\": 35.7147,\n"
                    "    \"longitude\": 139.7966,\n"
                    "    \"matching_interest\": \"interest_name\",\n"
                    "    \"why_recommended\": \"A brief explanation of why this matches their specific interest.\"\n"
                    "  }}\n"
                    "]\n"
                    "Rules:\n"
                    "1. Only suggest landmarks that match the traveler's interests.\n"
                    "2. Output ONLY raw JSON. No markdown backticks, no markdown code blocks."
                )
                human_message = (
                    "Destination: {destination}\n"
                    "Traveler Interests: {interests}\n"
                )

            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", human_message)
            ])
            
            chain = (prompt | llm).with_config({"run_name": "Activity_Curator"})
            
            invoke_params = {
                "destination": location,
                "interests": ", ".join(interests),
            }
            if curated_sights:
                invoke_params["sights_json"] = json.dumps(curated_sights, indent=2)
                
            response = await chain.ainvoke(invoke_params)
            
            content = getattr(response, "content", str(response))
            cleaned_content = clean_json_string(content)
            print("Cleaned Content: ", cleaned_content)
        # Verify valid JSON list
        try:
            json.loads(cleaned_content)
            return cleaned_content
        except json.JSONDecodeError as jde:
            print("\n--- DEBUG: LLM FAILED TO OUTPUT VALID JSON ---")
            print("Raw Content:")
            print(content)
            print("Cleaned Content:")
            print(cleaned_content)
            print("-----------------------------------------------\n")
            return json.dumps({
                "error": "LLM failed to output valid JSON",
                "raw_output": content,
                "details": str(jde)
            })
            
    except Exception as e:
        return json.dumps({"error": f"Failed to generate activities: {str(e)}"})


# ===== STANDALONE TEST RUNNER =====
if __name__ == "__main__":
    import asyncio

    async def test_agent():
        # Test interests matching Tokyo
        destination = "Broken Bow, Oklahoma"
        interests = ["history", "nature", "shopping"]
        
        print(f"Calling get_activities tool for: {destination}...")
        print(f"Interests: {interests}\n")
        
        # Invoke tool asynchronously using .ainvoke
        result_json = await get_activities.ainvoke({
            "location": destination,
            "interests": interests
        })
        
        parsed_result = json.loads(result_json)
        print("Curated Activities Response:")
        print(json.dumps(parsed_result, indent=2))

    asyncio.run(test_agent())
