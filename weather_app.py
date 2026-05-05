import requests
import json
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

CACHE_FILE    = "weather_cache.json"
CACHE_MAX_AGE = 600          # seconds — 10 minutes
BASE_URL      = "https://api.openweathermap.org/data/2.5"

# Weather condition code → display symbol
WEATHER_SYMBOLS = {
    "Clear":       "☀️ ",
    "Clouds":      "☁️ ",
    "Rain":        "🌧️ ",
    "Drizzle":     "🌦️ ",
    "Thunderstorm":"⛈️ ",
    "Snow":        "❄️ ",
    "Mist":        "🌫️ ",
    "Fog":         "🌫️ ",
    "Haze":        "🌫️ ",
}


# ─────────────────────────────────────────────
# Step 4: Load API key from .env file
# ─────────────────────────────────────────────
def load_api_key() -> str:
    load_dotenv()
    key = os.getenv("OPENWEATHER_API_KEY", "").strip()

    if not key:
        print("\n  ── Setup Required ──────────────────────────────")
        print("  No API key found. Do this once:")
        print("  1. Sign up free at https://openweathermap.org/api")
        print("  2. Copy your API key from your account dashboard")
        print("  3. Create a file called  .env  in this folder")
        print("  4. Add this line to it:  OPENWEATHER_API_KEY=your_key_here")
        print("  ────────────────────────────────────────────────\n")
        raise SystemExit

    return key


# ─────────────────────────────────────────────
# Step 5: Cache helpers
# ─────────────────────────────────────────────
def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def save_cache(cache: dict):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)


def get_cached(cache: dict, cache_key: str):
    """Return cached data if it exists and is still fresh, else None."""
    entry = cache.get(cache_key)
    if not entry:
        return None

    age = datetime.now(timezone.utc).timestamp() - entry["timestamp"]
    if age < CACHE_MAX_AGE:
        return entry["data"]

    return None   # stale


def set_cached(cache: dict, cache_key: str, data: dict):
    cache[cache_key] = {
        "timestamp": datetime.now(timezone.utc).timestamp(),
        "data": data,
    }
    save_cache(cache)


# ─────────────────────────────────────────────
# Step 6: Fetch current weather
# ─────────────────────────────────────────────
def fetch_current(city: str, api_key: str, units: str, cache: dict) -> dict:
    cache_key = f"current_{city.lower()}_{units}"
    cached    = get_cached(cache, cache_key)

    if cached:
        cached["_from_cache"] = True
        return cached

    url    = f"{BASE_URL}/weather"
    params = {"q": city, "appid": api_key, "units": units}

    try:
        response = requests.get(url, params=params, timeout=10)
    except requests.exceptions.ConnectionError:
        raise ConnectionError("No internet connection. Please check your network.")
    except requests.exceptions.Timeout:
        raise TimeoutError("Request timed out. The API took too long to respond.")

    if response.status_code == 404:
        raise ValueError(f"City '{city}' not found. Check the spelling and try again.")
    if response.status_code == 401:
        raise PermissionError("Invalid API key. Check your .env file.")
    if response.status_code != 200:
        raise RuntimeError(f"Unexpected API error (status {response.status_code}).")

    data = response.json()

    result = {
        "city":        data["name"],
        "country":     data["sys"]["country"],
        "temp":        data["main"]["temp"],
        "feels_like":  data["main"]["feels_like"],
        "temp_min":    data["main"]["temp_min"],
        "temp_max":    data["main"]["temp_max"],
        "humidity":    data["main"]["humidity"],
        "wind_speed":  data["wind"]["speed"],
        "description": data["weather"][0]["description"].capitalize(),
        "main":        data["weather"][0]["main"],
        "visibility":  data.get("visibility", 0) // 1000,  # convert m → km
        "_from_cache": False,
    }

    set_cached(cache, cache_key, result)
    return result


# ─────────────────────────────────────────────
# Step 7: Fetch 5-day forecast
# ─────────────────────────────────────────────
def fetch_forecast(city: str, api_key: str, units: str, cache: dict) -> list:
    cache_key = f"forecast_{city.lower()}_{units}"
    cached    = get_cached(cache, cache_key)

    if cached:
        return cached

    url    = f"{BASE_URL}/forecast"
    params = {"q": city, "appid": api_key, "units": units}

    try:
        response = requests.get(url, params=params, timeout=10)
    except requests.exceptions.ConnectionError:
        raise ConnectionError("No internet connection.")
    except requests.exceptions.Timeout:
        raise TimeoutError("Request timed out.")

    if response.status_code == 404:
        raise ValueError(f"City '{city}' not found.")
    if response.status_code == 401:
        raise PermissionError("Invalid API key.")
    if response.status_code != 200:
        raise RuntimeError(f"Unexpected API error (status {response.status_code}).")

    raw_list = response.json()["list"]

    # Group snapshots by date
    by_date = {}
    for snapshot in raw_list:
        date_str = snapshot["dt_txt"].split(" ")[0]   # "2024-03-15"
        by_date.setdefault(date_str, []).append(snapshot)

    # For each date, pick the snapshot closest to 12:00
    daily = []
    for date_str in sorted(by_date.keys()):
        snapshots = by_date[date_str]

        best = min(
            snapshots,
            key=lambda s: abs(
                datetime.strptime(s["dt_txt"], "%Y-%m-%d %H:%M:%S").hour - 12
            )
        )

        temps = [s["main"]["temp"] for s in snapshots]

        daily.append({
            "date":        date_str,
            "description": best["weather"][0]["description"].capitalize(),
            "main":        best["weather"][0]["main"],
            "temp":        best["main"]["temp"],
            "temp_min":    min(temps),
            "temp_max":    max(temps),
            "humidity":    best["main"]["humidity"],
            "wind_speed":  best["wind"]["speed"],
        })

    # Skip today if we already have current weather — keep next 5 days
    if len(daily) > 5:
        daily = daily[1:6]
    else:
        daily = daily[:5]

    set_cached(cache, cache_key, daily)
    return daily


# ─────────────────────────────────────────────
# Step 8: Display functions
# ─────────────────────────────────────────────
def unit_label(units: str) -> str:
    return "°C" if units == "metric" else "°F"


def wind_label(units: str) -> str:
    return "m/s" if units == "metric" else "mph"


def display_current(weather: dict, units: str):
    symbol = WEATHER_SYMBOLS.get(weather["main"], "🌡️ ")
    deg    = unit_label(units)
    wind   = wind_label(units)
    cached = "  (cached)" if weather.get("_from_cache") else ""

    print(f"\n  {'─'*48}")
    print(f"  {symbol} {weather['city']}, {weather['country']}{cached}")
    print(f"  {'─'*48}")
    print(f"  Condition   : {weather['description']}")
    print(f"  Temperature : {weather['temp']:.1f}{deg}  "
          f"(feels like {weather['feels_like']:.1f}{deg})")
    print(f"  High / Low  : {weather['temp_max']:.1f}{deg} / "
          f"{weather['temp_min']:.1f}{deg}")
    print(f"  Humidity    : {weather['humidity']}%")
    print(f"  Wind        : {weather['wind_speed']:.1f} {wind}")
    print(f"  Visibility  : {weather['visibility']} km")
    print(f"  {'─'*48}\n")


def display_forecast(forecast: list, units: str):
    deg  = unit_label(units)
    wind = wind_label(units)

    print(f"  {'─'*62}")
    print(f"  {'5-Day Forecast':^62}")
    print(f"  {'─'*62}")
    print(f"  {'Date':<13} {'Symbol':<5} {'Description':<20} "
          f"{'High':>6} {'Low':>6} {'Hum':>5}")
    print(f"  {'─'*62}")

    for day in forecast:
        symbol = WEATHER_SYMBOLS.get(day["main"], "🌡️ ")
        # Format date as "Mon Mar 15"
        date_fmt = datetime.strptime(day["date"], "%Y-%m-%d").strftime("%a %b %d")
        desc     = day["description"][:18]

        print(f"  {date_fmt:<13} {symbol:<5} {desc:<20} "
              f"{day['temp_max']:>5.1f}{deg} "
              f"{day['temp_min']:>5.1f}{deg} "
              f"{day['humidity']:>4}%")

    print(f"  {'─'*62}\n")


# ─────────────────────────────────────────────
# Step 9: Unit toggle helper
# ─────────────────────────────────────────────
def choose_units() -> str:
    while True:
        choice = input("  Units — (1) Celsius  (2) Fahrenheit: ").strip()
        if choice == "1":
            return "metric"
        if choice == "2":
            return "imperial"
        print("  Please enter 1 or 2.")


# ─────────────────────────────────────────────
# Step 10: Main loop
# ─────────────────────────────────────────────
def main():
    print("  === Weather App ===\n")

    api_key = load_api_key()
    cache   = load_cache()
    units   = choose_units()

    while True:
        print("\n  ─────────────────────────────")
        print("  1. Look up a city")
        print("  2. Switch units")
        print("  3. Quit")
        print("  ─────────────────────────────")

        choice = input("  Choose (1-3): ").strip()

        if choice == "1":
            city = input("  Enter city name: ").strip()
            if not city:
                print("  City name cannot be empty.")
                continue

            try:
                print(f"\n  Fetching weather for '{city}'...")

                current  = fetch_current(city, api_key, units, cache)
                forecast = fetch_forecast(city, api_key, units, cache)

                display_current(current, units)
                display_forecast(forecast, units)

            except (ValueError, PermissionError,
                    ConnectionError, TimeoutError, RuntimeError) as e:
                print(f"\n  Error: {e}\n")

        elif choice == "2":
            units = choose_units()
            print(f"  Units switched to "
                  f"{'Celsius' if units == 'metric' else 'Fahrenheit'}.")

        elif choice == "3":
            print("  Goodbye!")
            break

        else:
            print("  Invalid choice. Enter 1, 2, or 3.")


if __name__ == "__main__":
    main()