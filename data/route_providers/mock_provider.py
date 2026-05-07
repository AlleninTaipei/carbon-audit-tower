"""
Route Provider: Mock（Bezier Polyline）

使用 Quadratic Bezier 曲線與 Haversine × 道路係數模擬路徑與距離。
Waybill ID 作為隨機種子，確保輸出可重現。
"""

import math
import random
from datetime import datetime, timezone


ROAD_FACTOR = 1.30  # 台灣公路距離 / 直線距離平均比


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _bezier_polyline(
    o_lat: float, o_lon: float,
    d_lat: float, d_lon: float,
    n: int = 14,
    rng: random.Random | None = None,
) -> list[list[float]]:
    if rng is None:
        rng = random.Random()

    dlat = d_lat - o_lat
    dlon = d_lon - o_lon
    dist = math.sqrt(dlat ** 2 + dlon ** 2)

    if dist < 1e-5:
        return [[round(o_lat, 5), round(o_lon, 5)], [round(d_lat, 5), round(d_lon, 5)]]

    perp_lat = -dlon / dist
    perp_lon =  dlat / dist

    deviation = dist * rng.uniform(0.04, 0.11)
    ctrl_lat = (o_lat + d_lat) / 2 + deviation * perp_lat
    ctrl_lon = (o_lon + d_lon) / 2 + deviation * perp_lon

    coords = []
    for i in range(n):
        t = i / (n - 1)
        lat = (1 - t) ** 2 * o_lat + 2 * (1 - t) * t * ctrl_lat + t ** 2 * d_lat
        lon = (1 - t) ** 2 * o_lon + 2 * (1 - t) * t * ctrl_lon + t ** 2 * d_lon
        coords.append([round(lat, 5), round(lon, 5)])

    return coords


def compute_route(
    origin: tuple[float, float],
    dest: tuple[float, float],
    waybill_id: str,
    date: str | None,
    rng: random.Random,
) -> dict:
    """
    回傳欄位（與 TIM provider 介面一致）:
      distanceKm  int     公路距離（km）
      coords      list    Polyline 座標串（[[lat, lon], ...]）
      apiTs       str     模擬 API 呼叫時間戳（ISO 8601）
      routeSource str     資料來源標記（"MOCK_v1"）
    """
    o_lat, o_lon = origin
    d_lat, d_lon = dest

    straight_km = haversine_km(o_lat, o_lon, d_lat, d_lon)
    road_km = round(straight_km * ROAD_FACTOR)
    n_points = 14 if road_km > 100 else 10
    coords = _bezier_polyline(o_lat, o_lon, d_lat, d_lon, n=n_points, rng=rng)

    base_date = date or "2024-01-01"
    api_ts = (
        datetime.fromisoformat(base_date)
        .replace(
            hour=rng.randint(6, 10),
            minute=rng.randint(0, 59),
            second=rng.randint(0, 59),
            tzinfo=timezone.utc,
        )
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    return {
        "distanceKm":  road_km,
        "coords":      coords,
        "apiTs":       api_ts,
        "routeSource": "MOCK_v1",
    }
