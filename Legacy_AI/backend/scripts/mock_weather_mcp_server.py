"""
A self-contained MOCK WEATHER MCP server for testing the MCP integration —
no API keys, no external network, fully deterministic output.

It speaks the stdio transport, so connect to it from the API with a launcher
connection string (Docker / installed venv):

    python -m backend.scripts.mock_weather_mcp_server

or from a source checkout:

    uv run python -m backend.scripts.mock_weather_mcp_server

Exposed tools:
  - get_current_weather(city, units?)   -> current conditions for a city
  - get_forecast(city, days?, units?)    -> a multi-day forecast
  - get_weather_alerts(city)             -> active (mock) weather alerts
  - get_air_quality(city)                -> air-quality index + category
  - compare_weather(city_a, city_b)      -> side-by-side temperature comparison

All values are derived deterministically from the city name, so the same input
always returns the same output (handy for repeatable tests).
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Mock Weather MCP")


def _seed(city: str) -> int:
    """Deterministic pseudo-value from the city name (stable across runs)."""
    return sum(ord(ch) for ch in city.strip().lower()) if city.strip() else 0


def _temp_c(city: str) -> int:
    # Spread temperatures across a plausible -5°C..35°C band, deterministically.
    return (_seed(city) % 41) - 5


def _c_to_f(celsius: float) -> float:
    return round(celsius * 9 / 5 + 32, 1)


_CONDITIONS = [
    "sunny",
    "partly cloudy",
    "overcast",
    "light rain",
    "thunderstorms",
    "snow",
    "foggy",
]


@mcp.tool()
def get_current_weather(city: str, units: str = "celsius") -> str:
    """Get the current weather conditions for a city. units: 'celsius' or 'fahrenheit'."""
    c = _temp_c(city)
    seed = _seed(city)
    condition = _CONDITIONS[seed % len(_CONDITIONS)]
    humidity = 30 + (seed % 60)
    wind = 5 + (seed % 25)
    if units.lower().startswith("f"):
        temp = f"{_c_to_f(c)}°F"
    else:
        temp = f"{c}°C"
    return (
        f"Current weather in {city}: {temp}, {condition}. "
        f"Humidity {humidity}%, wind {wind} km/h. (mock data)"
    )


@mcp.tool()
def get_forecast(city: str, days: int = 3, units: str = "celsius") -> str:
    """Get a multi-day weather forecast for a city (1-7 days)."""
    days = max(1, min(int(days), 7))
    base = _temp_c(city)
    seed = _seed(city)
    lines = [f"{days}-day forecast for {city} (mock data):"]
    for d in range(days):
        hi = base + (d * 2) - 3 + (seed % 3)
        lo = hi - (4 + (seed % 4))
        condition = _CONDITIONS[(seed + d) % len(_CONDITIONS)]
        if units.lower().startswith("f"):
            hi_s, lo_s = f"{_c_to_f(hi)}°F", f"{_c_to_f(lo)}°F"
        else:
            hi_s, lo_s = f"{hi}°C", f"{lo}°C"
        lines.append(f"  Day {d + 1}: {condition}, high {hi_s} / low {lo_s}")
    return "\n".join(lines)


@mcp.tool()
def get_weather_alerts(city: str) -> str:
    """Return any active weather alerts/warnings for a city."""
    seed = _seed(city)
    if seed % 3 == 0:
        return f"No active weather alerts for {city}. (mock data)"
    alerts = ["Heat advisory", "High wind warning", "Flood watch", "Winter storm warning"]
    alert = alerts[seed % len(alerts)]
    return f"⚠ Active alert for {city}: {alert} in effect until further notice. (mock data)"


@mcp.tool()
def get_air_quality(city: str) -> str:
    """Get the current air quality index (AQI) and category for a city."""
    aqi = _seed(city) % 300
    if aqi <= 50:
        cat = "Good"
    elif aqi <= 100:
        cat = "Moderate"
    elif aqi <= 150:
        cat = "Unhealthy for sensitive groups"
    elif aqi <= 200:
        cat = "Unhealthy"
    else:
        cat = "Very unhealthy"
    return f"Air quality in {city}: AQI {aqi} ({cat}). (mock data)"


@mcp.tool()
def compare_weather(city_a: str, city_b: str) -> str:
    """Compare the current temperature of two cities and say which is warmer."""
    a, b = _temp_c(city_a), _temp_c(city_b)
    if a == b:
        verdict = f"{city_a} and {city_b} are the same temperature"
    else:
        warmer = city_a if a > b else city_b
        verdict = f"{warmer} is warmer by {abs(a - b)}°C"
    return f"{city_a}: {a}°C vs {city_b}: {b}°C — {verdict}. (mock data)"


if __name__ == "__main__":
    mcp.run(transport="stdio")
