"""
Generate an interactive map of the US state containing a given city.
"""
import csv
import sys
from pathlib import Path

import folium
import pandas as pd
import requests
from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.geocoders import Nominatim

# =============================================================================
# CHANGE STORE AND CITY - or pass as arguments: python main.py "Store Name" "City Name"
# =============================================================================
STORE = "Miami Beach"
CITY = "Miami"

# =============================================================================
# DATA FILE SETTINGS - path to your metrics file (CSV or Excel)
# =============================================================================
DATA_FILE = Path.home() / "Downloads" / "DMA_Store-report (2).xlsx"
# Column that contains the STORE name (used for lookup - enter the exact column header from your file)
DATA_STORE_COLUMN = "Store"
# Column that contains the CITY name (used for map placement and display)
DATA_CITY_COLUMN = "City"


# GeoJSON of US state boundaries (public dataset)
US_STATES_GEOJSON_URL = (
    "https://raw.githubusercontent.com/PublicaMundi/MappingAPI/master/data/geojson/us-states.json"
)

# Common state abbreviations for matching
_abbrev_to_full = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut",
    "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida",
    "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky",
    "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
    "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}


def _find_column(df, col_name: str, fallback_idx: int = 0):
    """Find column by name (case-insensitive), or return fallback."""
    target = col_name.strip().lower()
    for col in df.columns:
        if str(col).strip().lower() == target:
            return col
    return df.columns[fallback_idx] if len(df.columns) > fallback_idx else None


def load_store_data() -> dict[str, dict]:
    """
    Load store metrics from the data file (CSV or Excel).
    Returns a dict mapping store name (lowercase) to a dict of all metrics including city.
    """
    store_data = {}
    if not DATA_FILE.exists():
        return store_data

    if DATA_FILE.suffix.lower() in (".xlsx", ".xls"):
        try:
            df = pd.read_excel(DATA_FILE, sheet_name=0)
            df = df.astype(str)
            store_col = _find_column(df, DATA_STORE_COLUMN, 0)
            for _, row in df.iterrows():
                store_val = str(row.get(store_col, "")).strip()
                if store_val and store_val.lower() != "nan":
                    store_key = store_val.lower()
                    store_data[store_key] = {
                        str(k): str(v).strip() if pd.notna(v) and str(v) != "nan" else ""
                        for k, v in row.items()
                    }
        except Exception as e:
            print(f"Error reading Excel file: {e}")
        return store_data

    with open(DATA_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            store_val = row.get(DATA_STORE_COLUMN, row.get("Store", row.get("store", ""))).strip()
            if store_val:
                store_key = store_val.lower()
                store_data[store_key] = {k.strip(): str(v).strip() for k, v in row.items()}
    return store_data


def get_store_metrics(store_name: str, store_data: dict) -> dict | None:
    """Get metrics for a store (case-insensitive lookup)."""
    return store_data.get(store_name.strip().lower())


def get_city_from_metrics(metrics: dict) -> str:
    """Extract city from metrics dict using DATA_CITY_COLUMN."""
    city_col = DATA_CITY_COLUMN.strip().lower()
    for k, v in metrics.items():
        if str(k).strip().lower() == city_col and v:
            val = str(v).strip()
            if val and val.lower() != "nan":
                return val
    for alt in ("city", "City", "CITY"):
        v = metrics.get(alt)
        if v and str(v).strip().lower() != "nan":
            return str(v).strip()
    return ""


def format_metrics_popup(
    metrics: dict, store_name: str, city_name: str, state_name: str
) -> str:
    """Format store metrics as HTML for the map popup with Store and City shown separately."""
    lines = [
        f"<b>Store:</b> {store_name}",
        f"<b>City:</b> {city_name}",
        f"<b>State:</b> {state_name}",
        "<hr>",
    ]
    skip = {"store", "city", "state"}
    skip_lower = {s.lower() for s in skip}
    for key, value in metrics.items():
        key_lower = str(key).strip().lower()
        if key_lower not in skip_lower and value:
            label = str(key).replace("_", " ").title()
            lines.append(f"<b>{label}:</b> {value}")
    return "<br>".join(lines)


def geocode_city(city_name: str) -> tuple[float, float, str] | None:
    """Get coordinates and state for a US city. Returns (lat, lon, state_name) or None."""
    geolocator = Nominatim(user_agent="city_state_mapper")
    try:
        location = geolocator.geocode(f"{city_name}, USA", timeout=10)
        if not location:
            return None
        # Extract state from address components
        address = location.raw.get("address", {})
        state = address.get("state", "Unknown")
        return (location.latitude, location.longitude, state)
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"Geocoding error: {e}")
        return None


def get_state_geojson() -> dict | None:
    """Fetch US states GeoJSON from public URL."""
    try:
        response = requests.get(US_STATES_GEOJSON_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Could not fetch state boundaries: {e}")
        return None


def create_state_map(
    lat: float,
    lon: float,
    state_name: str,
    city_name: str,
    store_name: str,
    metrics: dict | None = None,
) -> folium.Map:
    """Create a Folium map centered on the state with store/city marker."""
    m = folium.Map(location=[lat, lon], zoom_start=7, tiles="CartoDB positron")

    geojson_data = get_state_geojson()
    if geojson_data:
        state_aliases = {state_name, _abbrev_to_full.get(state_name, state_name)}
        state_features = [
            f for f in geojson_data.get("features", [])
            if f.get("properties", {}).get("name") in state_aliases
        ]
        if state_features:
            state_geojson = {"type": "FeatureCollection", "features": state_features}
            folium.GeoJson(
                state_geojson,
                style_function=lambda x: {
                    "fillColor": "#3388ff",
                    "color": "#0066cc",
                    "weight": 2,
                    "fillOpacity": 0.2,
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=["name"],
                    aliases=["State:"],
                ),
            ).add_to(m)

    popup_text = (
        format_metrics_popup(metrics, store_name, city_name, state_name)
        if metrics
        else f"<b>Store:</b> {store_name}<br><b>City:</b> {city_name}<br><b>State:</b> {state_name}"
    )
    tooltip_text = f"{store_name} – {city_name}"
    folium.Marker(
        [lat, lon],
        popup=popup_text,
        tooltip=tooltip_text,
        icon=folium.Icon(color="red", icon="info-sign"),
    ).add_to(m)

    return m


def main():
    # Store and City can be set in script or passed as: python main.py "Store" "City"
    store_input = sys.argv[1] if len(sys.argv) > 1 else STORE
    city_input = sys.argv[2] if len(sys.argv) > 2 else CITY
    print(f"Store: {store_input}")
    print(f"City: {city_input}")

    store_data = load_store_data()
    metrics = get_store_metrics(store_input, store_data)
    store_name = store_input

    # Use city_input if provided; otherwise try to get city from store metrics
    if city_input and str(city_input).strip():
        city_for_map = str(city_input).strip()
        print(f"Using city from input: {city_for_map}")
    elif metrics:
        city_for_map = get_city_from_metrics(metrics)
        if city_for_map:
            print(f"Using city from data file: {city_for_map}")
        else:
            city_for_map = store_input
            print(f"City not found in data, using store name for map: {city_for_map}")
    else:
        city_for_map = store_input
        print(f"Store not in data file, using store name for map: {city_for_map}")

    if metrics:
        print(f"Loaded metrics for store '{store_name}' from {DATA_FILE.name}")
    else:
        print(f"Store '{store_name}' not found in {DATA_FILE.name}")

    result = geocode_city(city_for_map)
    if not result:
        print(f"Could not geocode location: {city_for_map}")
        sys.exit(1)

    lat, lon, state_name = result
    print(f"Map location: {city_for_map}, {state_name}")

    m = create_state_map(lat, lon, state_name, city_for_map, store_name, metrics)
    output_path = "state_map.html"
    m.save(output_path)
    print(f"Map saved to {output_path}. Open it in a browser to view.")


if __name__ == "__main__":
    main()
