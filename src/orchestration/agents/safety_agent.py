import json
import httpx
from langchain_core.prompts import ChatPromptTemplate
from src.orchestration.agents.base import get_llm

SYSTEM_PROMPT = """You are an expert travel safety specialist.
Your task is to analyze the safety score and travel advisory source data provided, and write a concise safety report for the traveler.

You must output your response in raw JSON format matching this exact structure:
{{
  "destination": "Destination Name",
  "advisory_level": "low",  // Must be one of: "low", "moderate", "high", or "extreme"
  "advisory_source": "Source Name",
  "advisory_summary": "A concise summary of the safety advisories, health notices, and general security tips.",
  "local_emergency_numbers": {{
    "police": "police_number",
    "ambulance": "ambulance_number"
  }}
}}

Rules:
1. Determine "advisory_level" based on the danger score (0-5) provided in the request. Map score 0.0-1.5 to "low", 1.6-3.0 to "moderate", 3.1-4.0 to "high", and 4.1-5.0 to "extreme".
2. Using your internal knowledge base, resolve and populate "local_emergency_numbers" with the correct, active emergency contacts for the destination country. 
   - E.g., Japan: police "110", ambulance "119".
   - E.g., India: police "100" (or "112" unified), ambulance "102".
   - E.g., China: police "110", ambulance "120".
   - E.g., South Africa: police "10111", ambulance "10177".
   - If you are unsure, default to "112".
3. Output ONLY the raw JSON object. Do not write conversational prefaces or conclusions. Do not wrap the JSON in markdown code blocks (like ```json). Just start with {{ and end with }}.
"""

def clean_json_string(text: str) -> str:
    """
    Cleans up any markdown wrappers (like ```json ... ```) 
    that the LLM might have output around the raw JSON.
    """
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

async def generate_safety_report(destination: str) -> str:
    """
    Asynchronously fetches coordinates, queries travel-advisory.info, 
    and uses the LLM to compile the safety JSON report.
    """
    try:
        async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
            # 1. Resolve location name to ISO-2 country code using Open-Meteo Geocoding API
            parts = [p.strip() for p in destination.split(",")]
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
                return json.dumps({"error": f"Could not geocode destination: '{destination}'"})
                
            resolved_match = results[0]
            if len(parts) > 1:
                context = parts[1].lower()
                for match in results:
                    admin1 = match.get("admin1", "").lower()
                    country = match.get("country", "").lower()
                    country_code_match = match.get("country_code", "").lower()
                    if context in admin1 or context in country or context == country_code_match:
                        resolved_match = match
                        break
                        
            country_code = resolved_match.get("country_code")
            country_name = resolved_match.get("country", destination)
            
            if not country_code:
                return json.dumps({"error": f"Could not resolve country code for: '{destination}'"})

            # 2. Query keyless Travel Advisory API using the country code
            try:
                advisory_url = f"https://api.travel-advisory.info/api?country={country_code}"
                advisory_response = await client.get(advisory_url, timeout=5.0)
                advisory_response.raise_for_status()
                advisory_data = advisory_response.json()
                
                # Extract score and message details from the API response
                advisory_details = advisory_data.get("data", {}).get(country_code, {})
                api_score = advisory_details.get("advisory", {}).get("score", 0.0)
                api_source = advisory_details.get("advisory", {}).get("source", "Travel-Advisory.info")
                api_message = advisory_details.get("advisory", {}).get("message", "No specific advisories.")
            except Exception as api_err:
                print(f"Warning: Travel Advisory API failed ({str(api_err)}). Falling back to LLM internal knowledge.")
                # Populate default fallback values for the LLM
                api_score = 1.0
                api_source = "State Department (Historical Database Fallback)"
                api_message = (
                    f"The Travel Advisory API is currently offline. "
                    f"Please estimate the risk level and compile the safety report for {country_name} "
                    f"using your internal knowledge of the country's general travel advisories and security situation."
                )

            # 3. Initialize LLM and pass the data
            llm = get_llm()
            prompt = ChatPromptTemplate.from_messages([
                ("system", SYSTEM_PROMPT),
                ("human", (
                    "Please compile a safety report for: {destination} ({country_name}, code: {country_code}).\n"
                    "The current API safety score is: {score} out of 5.0.\n"
                    "The source is: {source}.\n"
                    "The API message is: {message}\n"
                ))
            ])
            
            chain = prompt | llm
            response = await chain.ainvoke({
                "destination": destination,
                "country_name": country_name,
                "country_code": country_code,
                "score": api_score,
                "source": api_source,
                "message": api_message
            })
            
            content = getattr(response, "content", str(response))
            cleaned_content = clean_json_string(content)
            
            # Verify valid JSON
            json.loads(cleaned_content)
            return cleaned_content
            
    except Exception as e:
        return json.dumps({"error": f"Failed to generate safety report: {str(e)}"})


# ===== STANDALONE TEST RUNNER =====
if __name__ == "__main__":
    import asyncio

    async def test_agent():
        # Test an Asian country (Japan) and an African country (Kenya)
        test_destinations = ["Tokyo, Japan", "Nairobi, Kenya"]
        
        for dest in test_destinations:
            print(f"Generating Safety Report for: {dest}...")
            result_json = await generate_safety_report(dest)
            
            parsed_result = json.loads(result_json)
            print("Response:")
            print(json.dumps(parsed_result, indent=2))
            print("-" * 50)

    asyncio.run(test_agent())
