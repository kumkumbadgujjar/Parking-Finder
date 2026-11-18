"""
parking_service.py
Fetches real parking locations via Google Places API (New) Nearby Search:
  POST https://places.googleapis.com/v1/places:searchNearby
Forces English responses (languageCode="en", regionCode="IN") and validates
ZERO_RESULTS, REQUEST_DENIED / PERMISSION_DENIED, invalid payloads, and network errors.
Never generates fake parking names, random coordinates, or unverified availability.
"""

import math
from dataclasses import dataclass
from typing import List, Optional

import requests
from geopy.distance import geodesic

from location_service import SOLUTION_ID, load_env_key

PLACES_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"
FIELD_MASK = (
    "places.id,"
    "places.displayName,"
    "places.formattedAddress,"
    "places.location,"
    "places.googleMapsUri,"
    "places.googleMapsLinks"
)


@dataclass
class ParkingLocation:
    place_id: str
    name: str
    address: str
    latitude: float
    longitude: float
    distance_km: float
    google_maps_uri: str
    directions_uri: str
    data_source: str
    availability_status: str


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance fallback in km."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compute_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in km using geopy geodesic, falling back to haversine."""
    try:
        return float(geodesic((lat1, lon1), (lat2, lon2)).kilometers)
    except Exception:
        return haversine_km(lat1, lon1, lat2, lon2)


def fetch_google_nearby_parking(
    lat: float,
    lon: float,
    radius_meters: float = 3000.0,
) -> tuple[List[ParkingLocation], Optional[str]]:
    """
    Search for genuine parking facilities using Google Places API (New) Nearby Search.
    Strictly checks API errors and ZERO_RESULTS; never returns fabricated data.
    """
    api_key = load_env_key()
    if not api_key:
        return [], (
            "REQUEST_DENIED: GOOGLE_MAPS_API_KEY is not set. "
            "Add GOOGLE_MAPS_API_KEY to your environment variables or .env file "
            "with Places API (New) enabled."
        )

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
        "X-Goog-Maps-Solution-ID": SOLUTION_ID,
    }

    payload = {
        "includedTypes": ["parking"],
        "maxResultCount": 20,
        "rankPreference": "DISTANCE",
        "languageCode": "en",
        "regionCode": "IN",
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": float(lat),
                    "longitude": float(lon),
                },
                "radius": float(radius_meters),
            }
        },
    }

    try:
        resp = requests.post(
            PLACES_NEARBY_URL,
            headers=headers,
            json=payload,
            timeout=12,
        )
    except requests.ConnectionError:
        return [], "Network error: Unable to connect to Google Places API."
    except requests.Timeout:
        return [], "Network timeout: Google Places API did not respond in time."
    except requests.RequestException as exc:
        return [], f"Network error calling Google Places API: {exc}"

    try:
        data = resp.json()
    except ValueError:
        return [], f"Invalid response from Google Places API (HTTP {resp.status_code})."

    if resp.status_code != 200:
        err = data.get("error", {}) if isinstance(data, dict) else {}
        status = err.get("status") or f"HTTP_{resp.status_code}"
        message = err.get("message") or "API request failed."
        if resp.status_code in (401, 403):
            return [], (
                f"REQUEST_DENIED ({status}): {message}. "
                "Verify that GOOGLE_MAPS_API_KEY is valid and Places API (New) is enabled."
            )
        return [], f"Google Places API error ({status}): {message}"

    if not isinstance(data, dict):
        return [], "Invalid response structure from Google Places API."

    raw_places = data.get("places")
    if not raw_places:
        return [], f"ZERO_RESULTS: No parking facilities found within {int(radius_meters)} m."

    results: List[ParkingLocation] = []
    for place in raw_places:
        loc = place.get("location") or {}
        p_lat = loc.get("latitude")
        p_lon = loc.get("longitude")
        if p_lat is None or p_lon is None:
            continue

        p_lat = float(p_lat)
        p_lon = float(p_lon)
        place_id = str(place.get("id") or "")
        display_name_obj = place.get("displayName") or {}
        name = str(display_name_obj.get("text") or "Parking Facility")
        address = str(place.get("formattedAddress") or "Address unavailable")
        dist_km = compute_distance_km(lat, lon, p_lat, p_lon)

        maps_uri = str(
            place.get("googleMapsUri")
            or f"https://www.google.com/maps/search/?api=1&query={p_lat},{p_lon}&query_place_id={place_id}"
        )
        links = place.get("googleMapsLinks") or {}
        directions_uri = str(
            links.get("directionsUri")
            or f"https://www.google.com/maps/dir/?api=1&origin={lat},{lon}&destination={p_lat},{p_lon}&destination_place_id={place_id}"
        )

        results.append(
            ParkingLocation(
                place_id=place_id,
                name=name,
                address=address,
                latitude=p_lat,
                longitude=p_lon,
                distance_km=dist_km,
                google_maps_uri=maps_uri,
                directions_uri=directions_uri,
                data_source="Google Places API (New)",
                availability_status="Availability unknown (No verified real-time occupancy feed)",
            )
        )

    if not results:
        return [], f"ZERO_RESULTS: No valid parking coordinates returned within {int(radius_meters)} m."

    results.sort(key=lambda item: item.distance_km)
    return results, None
