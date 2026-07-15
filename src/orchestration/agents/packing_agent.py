import json
from typing import Any
from langchain_core.prompts import ChatPromptTemplate
from src.orchestration.agents.base import get_llm

SYSTEM_PROMPT = """You are an expert travel packing assistant. 
Your goal is to analyze the trip details (destination, interests, and weather forecast) and generate a customized packing list.

You must output your response in raw JSON format matching this exact structure:
{{
  "base_items": ["item1", "item2", ...],
  "weather_driven_items": ["item1", "item2", ...],
  "activity_driven_items": ["item1", "item2", ...]
}}

Follow these rules:
1. "base_items" must include general essentials (passport, toiletries, chargers) tailored slightly for the destination.
2. "weather_driven_items" must include items derived directly from the provided weather forecast (e.g. umbrella for rain, warm jacket for cold, sunscreen/sunglasses for hot/sunny weather).
3. "activity_driven_items" must include items derived directly from the user's interests (e.g. hiking boots for hiking, camera for photography, smart-casual wear for nightlife).
4. Output ONLY the raw JSON object. Do not write conversational prefaces or conclusions. Do not wrap the JSON in markdown code blocks (like ```json). Just start with {{ and end with }}.
"""

def clean_json_string(text: Any) -> str:
    """
    Cleans up any markdown wrappers (like ```json ... ```) 
    that the LLM might have output around the raw JSON.
    """
    if isinstance(text, list):
        text = "".join([block.get("text", "") if isinstance(block, dict) else str(block) for block in text])
    elif not isinstance(text, str):
        text = str(text)

    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

async def generate_packing_list(destination: str, interests: list[str], weather_forecast_json: str) -> str:
    """
    Asynchronously invokes the LLM to generate the customized packing lists
    based on destination, interests, and weather data.
    """
    # 1. Initialize the LLM client configured in your .env file
    llm = get_llm()
    
    # 2. Build the prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", (
            "Please generate a packing list for a trip to: {destination}\n"
            "My interests are: {interests}\n"
            "The weather forecast is: {weather_forecast}\n"
        ))
    ])
    
    # 3. Create the execution chain
    chain = (prompt | llm).with_config({"run_name": "Packing_List_Generator"})
    
    try:
        # 4. Invoke the model
        response = await chain.ainvoke({
            "destination": destination,
            "interests": ", ".join(interests),
            "weather_forecast": weather_forecast_json
        })
        
        # Extract and clean string content
        content = getattr(response, "content", str(response))
        cleaned_content = clean_json_string(content)
        
        # Verify it parses as valid JSON
        json.loads(cleaned_content)
        return cleaned_content
        
    except json.JSONDecodeError as jde:
        return json.dumps({
            "error": "LLM failed to output valid JSON", 
            "raw_output": content,
            "details": str(jde)
        })
    except Exception as e:
        return json.dumps({"error": f"Failed to generate packing list: {str(e)}"})


# ===== STANDALONE TEST RUNNER =====
if __name__ == "__main__":
    import asyncio

    async def test_agent():
        # 1. Sample inputs
        destination = "Tokyo, Japan"
        interests = ["hiking", "anime", "nightlife"]
        
        # 2. Simulated weather forecast (matching Weather Agent output)
        sample_weather = json.dumps([
            {
                "date": "2026-07-20",
                "description": "Light rain/Cloudy (High: 84F, Low: 70F)",
                "temperature": 77,
                "rainfall_mm": 3.2,
                "outdoor_feasible": True
            },
            {
                "date": "2026-07-21",
                "description": "Heavy rain/Stormy (High: 78F, Low: 66F)",
                "temperature": 72,
                "rainfall_mm": 12.0,
                "outdoor_feasible": False
            }
        ])

        print(f"Generating packing list for {destination}...")
        print(f"Interests: {interests}")
        print("Feeding in rainy weather forecast...\n")

        # 3. Call the agent
        result_json = await generate_packing_list(destination, interests, sample_weather)
        
        # 4. Print response
        parsed_result = json.loads(result_json)
        print("Generated Packing List Response:")
        print(json.dumps(parsed_result, indent=2))

    asyncio.run(test_agent())
