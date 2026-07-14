
from langchain_core.tools import tool
import httpx
import json
import asyncio
from datetime import datetime, timedelta


@tool
async def get_weather_forecast(location: str, dates: list[str]) -> str:
    """
    Fetches the daily weather conditions, temperatures (min/max), rainfall, 
    and outdoor feasibility for a location accross a list of dates.
    
    Input Examples:
    location = "Tokyo, Japan"
    dates = ["2026-10-01", "2026-10-02", "2026-10-03"]

    Returns:
    A JSON formatted string containing an array of daily forcasts.
    
    Example of response:
    [
        {
            "date": "2026-10-01",
            "description": "Sunny with a high of 75F and a low of 60F",
            "temperature": 68,
            "rainfall_mm": 0,
            "outdoor_feasible": true
        },
        {
            "date": "2026-10-02",
            "description": "Cloudy with a high of 70F and a low of 58F",
            "temperature": 64,
            "rainfall_mm": 2,
            "outdoor_feasible": false
        }
    ]
    """
    try:
        async with httpx.AsyncClient() as client:
            # 1. Resolve location string to geographic coordinates
            geocode_url = "https://geocoding-api.open-meteo.com/v1/search"
            geocode_response = await client.get(
                geocode_url, 
                params={"name": location, "count": 1},
                timeout=10.0
            )
            geocode_response.raise_for_status()
            geocode_data = geocode_response.json()
            
            # Verify coordinates were returned
            if not geocode_data.get("results"):
                return json.dumps({"error": f"Could not geocode location: '{location}'"})
                
            first_match = geocode_data["results"][0]
            lat = first_match["latitude"]
            lon = first_match["longitude"]
            
            # 2. Fetch the weather forecast for resolved coordinates
            forecast_url = "https://api.open-meteo.com/v1/forecast"
            forecast_params = {
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                "temperature_unit": "fahrenheit",
                "timezone": "auto",
                "forcast+days": "14"
            }
            forecast_response = await client.get(
                forecast_url, 
                params=forecast_params,
                timeout=10.0
            )
            forecast_response.raise_for_status()
            forecast_data = forecast_response.json()
            
            daily_data = forecast_data.get("daily", {})
            times = daily_data.get("time", [])
            max_temps = daily_data.get("temperature_2m_max", [])
            min_temps = daily_data.get("temperature_2m_min", [])
            precipitations = daily_data.get("precipitation_sum", [])
            
            # 3. Match forecasts to requested dates
            forecasts = []
            for target_date in dates:
                if target_date in times:
                    idx = times.index(target_date)
                    high = int(round(max_temps[idx]))
                    low = int(round(min_temps[idx]))
                    avg_temp = (high + low) // 2
                    rain_mm = precipitations[idx]
                    
                    # Feasibility threshold: less than 5mm precipitation is considered outdoor-friendly
                    outdoor_feasible = rain_mm < 5.0
                    
                    if rain_mm == 0:
                        desc = f"Clear/Sunny (High: {high}F, Low: {low}F)"
                    elif rain_mm < 5.0:
                        desc = f"Light rain/Cloudy (High: {high}F, Low: {low}F)"
                    else:
                        desc = f"Heavy rain/Stormy (High: {high}F, Low: {low}F)"
                        
                    forecasts.append({
                        "date": target_date,
                        "description": desc,
                        "temperature": avg_temp,
                        "rainfall_mm": rain_mm,
                        "outdoor_feasible": outdoor_feasible
                    })
                else:
                    # Fallback for requested dates outside the API forecast window (usually 7 days)
                    forecasts.append({
                        "date": target_date,
                        "description": "Unknown/Forecast unavailable (Out of forecast range)",
                        "temperature": 65,
                        "rainfall_mm": 0,
                        "outdoor_feasible": True
                    })
                    
            return json.dumps(forecasts)
            
    except Exception as e:
        return json.dumps({"error": f"Failed to retrieve weather data: {str(e)}"})


if __name__ == "__main__":
    async def test_tool():
        next_week_start_str = (datetime.now() + timedelta(days=6)).strftime("%Y-%m-%d")
        next_week_day_two_str = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        dates_to_check = [next_week_start_str, next_week_day_two_str]
        
        print(f"Calling line Open-METEO API FOR TOKYO JAPAN ON {next_week_start_str} and {next_week_day_two_str}\n")
        
    
        result_json = await get_weather_forecast.ainvoke({
            "location": "Tokyo, Japan",
            "dates": dates_to_check
        })

        pareset_result = json.loads(result_json)
        print("\nAPI Response:")
        print(json.dumps(pareset_result, indent=2))

    asyncio.run(test_tool())
    
