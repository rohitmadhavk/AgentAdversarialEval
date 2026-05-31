"""
tools.py — three tools and their schemas.

Each tool is a plain function. TOOL_SCHEMAS is the single source of truth
for what the LLM sees. TOOL_FUNCTIONS is the dispatch map.

Fault injection lives entirely in fault.py. These functions have no knowledge
of test infrastructure. To inject failures, wrap TOOL_FUNCTIONS with
fault.wrap_tools() before passing to run_turn().
"""

import httpx

from db import get_connection, init_db, TaskStatus, validate_status


# ── tool 1: manage_tasks (stateful) ───────────────────────────────────────────

def manage_tasks(action: str, title: str = "", task_id: int = 0) -> dict:
    init_db()

    def _add(conn):
        if not title:
            return {"error": "title required"}
        cur = conn.execute(
            "INSERT INTO tasks (title) VALUES (?) RETURNING id, title, status, created",
            (title,),
        )
        row = dict(cur.fetchone())
        conn.commit()
        return {"status": "added", "task": row}

    def _list(conn):
        rows = conn.execute("SELECT id, title, status, created FROM tasks ORDER BY id").fetchall()
        return {"tasks": [dict(r) for r in rows]}

    def _complete(conn):
        if not task_id:
            return {"error": "task_id required"}
        conn.execute("UPDATE tasks SET status=? WHERE id=?", (validate_status(TaskStatus.DONE), task_id))
        conn.commit()
        return {"status": "completed", "task_id": task_id}

    def _delete(conn):
        if not task_id:
            return {"error": "task_id required"}
        conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        conn.commit()
        return {"status": "deleted", "task_id": task_id}

    _dispatch = {"add": _add, "list": _list, "complete": _complete, "delete": _delete}

    fn = _dispatch.get(action.strip().lower())
    if fn is None:
        return {"error": f"unknown action '{action}'. Use: {', '.join(_dispatch)}"}

    with get_connection() as conn:
        return fn(conn)


# ── tool 2: convert_units (stateless) ────────────────────────────────────────
#
# Pure lookup-table unit conversion — no eval(), no security surface.
# Temperature requires offset arithmetic so it is special-cased; all other
# conversions are a single ratio applied from a dict keyed on (from, to).

_UNIT_CONVERSIONS: dict[tuple[str, str], object] = {
    # distance
    ("km",     "miles"):  lambda v: v * 0.621371,
    ("miles",  "km"):     lambda v: v * 1.60934,
    ("m",      "ft"):     lambda v: v * 3.28084,
    ("ft",     "m"):      lambda v: v / 3.28084,
    ("cm",     "inches"): lambda v: v / 2.54,
    ("inches", "cm"):     lambda v: v * 2.54,
    ("km",     "m"):      lambda v: v * 1000,
    ("m",      "km"):     lambda v: v / 1000,
    # mass
    ("kg",  "lbs"): lambda v: v * 2.20462,
    ("lbs", "kg"):  lambda v: v / 2.20462,
    ("g",   "oz"):  lambda v: v / 28.3495,
    ("oz",  "g"):   lambda v: v * 28.3495,
    ("kg",  "g"):   lambda v: v * 1000,
    ("g",   "kg"):  lambda v: v / 1000,
    # volume
    ("liters",  "gallons"): lambda v: v * 0.264172,
    ("gallons", "liters"):  lambda v: v * 3.78541,
    ("ml",      "cups"):    lambda v: v / 236.588,
    ("cups",    "ml"):      lambda v: v * 236.588,
    ("liters",  "ml"):      lambda v: v * 1000,
    ("ml",      "liters"):  lambda v: v / 1000,
    # speed
    ("kmh", "mph"): lambda v: v * 0.621371,
    ("mph", "kmh"): lambda v: v * 1.60934,
}

_TEMP_UNITS = frozenset({"celsius", "fahrenheit", "kelvin"})
_SUPPORTED_UNITS = sorted({u for pair in _UNIT_CONVERSIONS for u in pair} | _TEMP_UNITS)


def _to_celsius(value: float, unit: str) -> float:
    if unit == "fahrenheit":
        return (value - 32) * 5 / 9
    if unit == "kelvin":
        return value - 273.15
    return value


def _from_celsius(celsius: float, unit: str) -> float:
    if unit == "fahrenheit":
        return celsius * 9 / 5 + 32
    if unit == "kelvin":
        return celsius + 273.15
    return celsius


def convert_units(value: float, from_unit: str, to_unit: str) -> dict:
    f = from_unit.strip().lower()
    t = to_unit.strip().lower()

    if f == t:
        return {"value": value, "from_unit": from_unit, "to_unit": to_unit, "result": value}

    # Temperature: offset arithmetic, cannot be expressed as a ratio
    if f in _TEMP_UNITS or t in _TEMP_UNITS:
        if f not in _TEMP_UNITS or t not in _TEMP_UNITS:
            return {"error": f"Cannot mix temperature and non-temperature units: '{from_unit}' → '{to_unit}'"}
        result = _from_celsius(_to_celsius(value, f), t)
        return {"value": value, "from_unit": from_unit, "to_unit": to_unit, "result": round(result, 4)}

    key = (f, t)
    if key not in _UNIT_CONVERSIONS:
        return {
            "error": (
                f"Unsupported conversion: '{from_unit}' → '{to_unit}'. "
                f"Supported units: {', '.join(_SUPPORTED_UNITS)}"
            )
        }

    result = _UNIT_CONVERSIONS[key](value)
    return {"value": value, "from_unit": from_unit, "to_unit": to_unit, "result": round(result, 4)}


# ── tool 3: get_weather (stateless, HTTP) ─────────────────────────────────────

_CITIES: dict[str, tuple[float, float]] = {
    "new york":    (40.7128, -74.0060),
    "chicago":     (41.8781, -87.6298),
    "los angeles": (34.0522, -118.2437),
    "miami":       (25.7617,  -80.1918),
    "seattle":     (47.6062, -122.3321),
    "houston":     (29.7604,  -95.3698),
    "phoenix":     (33.4484, -112.0740),
    "denver":      (39.7392, -104.9903),
    "boston":      (42.3601,  -71.0589),
    "atlanta":     (33.7490,  -84.3880),
}

_NWS_HEADERS = {"User-Agent": "agent-eval/1.0 (eval-harness)", "Accept": "application/geo+json"}


def _nws_get(url: str) -> dict | None:
    try:
        r = httpx.get(url, headers=_NWS_HEADERS, timeout=30.0)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def get_weather(city: str) -> dict:
    key = city.strip().lower()
    if key not in _CITIES:
        return {"error": f"'{city}' not supported. Try: {', '.join(sorted(_CITIES))}"}
    lat, lon = _CITIES[key]

    # Step 1: resolve grid metadata
    meta = _nws_get(f"https://api.weather.gov/points/{lat},{lon}")
    if not meta:
        return {"error": "weather fetch failed: could not reach NWS points endpoint"}

    # Step 2: fetch the forecast
    forecast_data = _nws_get(meta["properties"]["forecast"])
    if not forecast_data:
        return {"error": "weather fetch failed: could not reach NWS forecast endpoint"}

    period = forecast_data["properties"]["periods"][0]
    temp_f = period["temperature"]
    temp_c = round((temp_f - 32) * 5 / 9, 1)
    wind_str = period.get("windSpeed", "0 mph")
    wind_mph = float(wind_str.split()[0]) if wind_str else 0.0
    return {
        "city": city.title(),
        "temperature_c": temp_c,
        "wind_speed_kmh": round(wind_mph * 1.60934, 1),
        "condition": period.get("detailedForecast", "Unknown"),
    }
# ── schemas (Gemini function-declaration format) ───────────────────────────────

TOOL_SCHEMAS = [
    {
        "name": "manage_tasks",
        "description": (
            "Manage a persistent to-do list. Use for tasks, todos, reminders, checklists. "
            "Actions: add (needs title), list, complete (needs task_id), delete (needs task_id). "
            "Only include title for add; only include task_id for complete/delete; "
            "omit both for list."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action":  {"type": "string", "enum": ["add", "list", "complete", "delete"]},
                "title":   {"type": "string",  "description": "Task title. Only include for action=add."},
                "task_id": {"type": "integer", "description": "Task ID. Only include for action=complete or action=delete."},
            },
            "required": ["action"],
        },
    },
    {
        "name": "convert_units",
        "description": (
            "Convert a numeric value between units of measurement. "
            "Supported categories: "
            "temperature (celsius, fahrenheit, kelvin), "
            "distance (km, miles, m, ft, cm, inches), "
            "mass (kg, lbs, g, oz), "
            "volume (liters, gallons, ml, cups), "
            "speed (kmh, mph). "
            "Only call this tool when the numeric value is already present in the conversation. "
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "value":     {"type": "number", "description": "Numeric value to convert."},
                "from_unit": {"type": "string", "description": "Source unit, e.g. 'km', 'celsius', 'kg'."},
                "to_unit":   {"type": "string", "description": "Target unit, e.g. 'miles', 'fahrenheit', 'lbs'."},
            },
            "required": ["value", "from_unit", "to_unit"],
        },
    },
    {
        "name": "get_weather",
        "description": (
            "Get CURRENT real-time weather for a supported US city: temperature (°C), wind speed, condition. "
            "Supported cities: New York, Chicago, Los Angeles, Miami, Seattle, Houston, "
            "Phoenix, Denver, Boston, Atlanta. "
            "Do NOT use for unsupported cities, historical weather, or any non-weather query. "
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "US city name, e.g. 'New York', 'Chicago'."},
            },
            "required": ["city"],
        },
    },
]

TOOL_FUNCTIONS = {
    "manage_tasks":  manage_tasks,
    "convert_units": convert_units,
    "get_weather":   get_weather,
}