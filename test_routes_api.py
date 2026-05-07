import os
import requests
from pathlib import Path

with open(Path(__file__).parent / ".env") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.split("#")[0].strip())

r = requests.post(
    "https://routes.googleapis.com/directions/v2:computeRoutes",
    json={
        "origin":      {"location": {"latLng": {"latitude": 25.07, "longitude": 121.58}}},
        "destination": {"location": {"latLng": {"latitude": 22.60, "longitude": 120.30}}},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_UNAWARE",
        "computeAlternativeRoutes": False,
    },
    headers={
        "Content-Type":    "application/json",
        "X-Goog-Api-Key":  os.environ.get("GOOGLE_ROUTES_API_KEY") or os.environ["GOOGLE_MAPS_API_KEY"],
        "X-Goog-FieldMask": "routes.distanceMeters",
    },
    timeout=10,
)

if r.status_code == 200:
    km = round(r.json()["routes"][0]["distanceMeters"] / 1000)
    print(f"HTTP 200 — ✅ 已生效，測試路線距離：{km} km")
else:
    print(f"HTTP {r.status_code} — {r.json()['error']['message'][:100]}")
