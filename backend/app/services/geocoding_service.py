"""Real geocoding + distance via Mapbox, with a great-circle fallback.

Domestic/road vehicles (velo, scooter, voiture, camionnette, camion) use the
Mapbox Directions API (driving profile) for a real road distance.
Intercontinental modes (avion, bateau) use great-circle (haversine) distance
directly, since there is no road route across an ocean and flight/shipping
distance tracks the great-circle distance closely.

If MAPBOX_ACCESS_TOKEN is not configured, or the Mapbox API call fails
(no network, address not found, no route, quota exceeded, ...), this falls
back to a haversine estimate between geocoded points, and finally to a fixed
default if geocoding itself is unavailable — the booking flow must never
hard-fail just because a third-party API is down.
"""

import math
from typing import Optional, Tuple
from urllib.parse import quote

import httpx

from app.config import get_settings

settings = get_settings()

MAPBOX_GEOCODE_URL = "https://api.mapbox.com/geocoding/v5/mapbox.places/{query}.json"
MAPBOX_DIRECTIONS_URL = "https://api.mapbox.com/directions/v5/mapbox/driving/{coords}"

ROAD_VEHICLES = {"velo", "scooter", "voiture", "camionnette", "camion"}
DEFAULT_FALLBACK_KM = 25.0


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


async def geocode(query: str) -> Optional[Tuple[float, float]]:
    """Returns (lat, lng) for a free-text address/city, or None if unavailable."""
    if not settings.mapbox_access_token or not query:
        return None
    url = MAPBOX_GEOCODE_URL.format(query=quote(query))
    params = {"access_token": settings.mapbox_access_token, "limit": 1}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            features = data.get("features") or []
            if not features:
                return None
            lng, lat = features[0]["center"]
            return (lat, lng)
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        return None


async def _driving_distance_km(pickup: Tuple[float, float], dropoff: Tuple[float, float]) -> Optional[float]:
    if not settings.mapbox_access_token:
        return None
    coords = f"{pickup[1]},{pickup[0]};{dropoff[1]},{dropoff[0]}"
    url = MAPBOX_DIRECTIONS_URL.format(coords=coords)
    params = {"access_token": settings.mapbox_access_token, "overview": "false"}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            routes = data.get("routes") or []
            if not routes:
                return None
            return round(routes[0]["distance"] / 1000.0, 1)
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        return None


async def estimate_distance_km(
    pickup_query: str,
    dropoff_query: str,
    vehicle: str,
) -> dict:
    """Returns {distance_km, source, pickup_coordinates, dropoff_coordinates}."""
    pickup_coords = await geocode(pickup_query)
    dropoff_coords = await geocode(dropoff_query)

    if not pickup_coords or not dropoff_coords:
        return {
            "distance_km": DEFAULT_FALLBACK_KM,
            "source": "fallback",
            "pickup_coordinates": None,
            "dropoff_coordinates": None,
        }

    if pickup_coords == dropoff_coords:
        return {
            "distance_km": 3.0,
            "source": "same_point",
            "pickup_coordinates": list(pickup_coords),
            "dropoff_coordinates": list(dropoff_coords),
        }

    if vehicle in ROAD_VEHICLES:
        driving_km = await _driving_distance_km(pickup_coords, dropoff_coords)
        if driving_km is not None:
            return {
                "distance_km": driving_km,
                "source": "geocoded_driving",
                "pickup_coordinates": list(pickup_coords),
                "dropoff_coordinates": list(dropoff_coords),
            }

    # avion / bateau, or driving API unavailable: great-circle distance
    great_circle_km = round(
        _haversine_km(pickup_coords[0], pickup_coords[1], dropoff_coords[0], dropoff_coords[1]), 1
    )
    return {
        "distance_km": great_circle_km,
        "source": "great_circle",
        "pickup_coordinates": list(pickup_coords),
        "dropoff_coordinates": list(dropoff_coords),
    }
