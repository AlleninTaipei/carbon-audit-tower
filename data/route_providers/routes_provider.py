"""
Route Provider: Google Routes API v2

呼叫 Google Routes API 取得真實公路距離與路徑 Polyline。
前置條件：
  - Google Cloud Console 已啟用 Routes API
  - .env 設有 GOOGLE_MAPS_API_KEY
"""

import os
import random
from datetime import datetime, timezone

import requests

_ENDPOINT  = "https://routes.googleapis.com/directions/v2:computeRoutes"
_FIELDMASK = "routes.distanceMeters,routes.polyline.encodedPolyline"


def _decode_polyline(encoded: str) -> list[list[float]]:
    """Google Encoded Polyline Algorithm → [[lat, lon], ...]"""
    index, lat, lng = 0, 0, 0
    coords = []
    while index < len(encoded):
        for is_lng in (False, True):
            shift, result = 0, 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if is_lng:
                lng += delta
                coords.append([round(lat / 1e5, 5), round(lng / 1e5, 5)])
            else:
                lat += delta
    return coords


def compute_route(
    origin: tuple[float, float],
    dest: tuple[float, float],
    waybill_id: str,
    date: str | None,
    rng: random.Random,
) -> dict:
    """
    回傳欄位（與 mock_provider 介面一致）:
      distanceKm  int     公路距離（km）
      coords      list    Polyline 座標串（[[lat, lon], ...]）
      apiTs       str     API 呼叫時間戳（ISO 8601）
      routeSource str     "ROUTES_API_v2"
    """
    api_key = os.environ.get("GOOGLE_ROUTES_API_KEY") or os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        raise EnvironmentError("GOOGLE_ROUTES_API_KEY（或 GOOGLE_MAPS_API_KEY）未設定，無法呼叫 Routes API")

    payload = {
        "origin": {
            "location": {"latLng": {"latitude": origin[0], "longitude": origin[1]}}
        },
        "destination": {
            "location": {"latLng": {"latitude": dest[0], "longitude": dest[1]}}
        },
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_UNAWARE",
        "computeAlternativeRoutes": False,
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": _FIELDMASK,
    }

    resp = requests.post(_ENDPOINT, json=payload, headers=headers, timeout=15)
    resp.raise_for_status()

    route = resp.json()["routes"][0]
    distance_km = round(route["distanceMeters"] / 1000)
    coords = _decode_polyline(route["polyline"]["encodedPolyline"])
    api_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "distanceKm":  distance_km,
        "coords":      coords,
        "apiTs":       api_ts,
        "routeSource": "ROUTES_API_v2",
    }
