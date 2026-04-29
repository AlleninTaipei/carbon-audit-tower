"""
Step 3 — 路線計算（Mock）
Input : output/cleaned_records.json
Output: output/routes_computed.json

使用 Quadratic Bezier 曲線模擬路徑 Polyline。
距離 = Haversine 直線距離 × 道路係數 1.3（台灣公路平均值）。
Waybill ID 作為隨機種子，確保輸出可重現。
"""

import json
import math
import hashlib
import random
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent

# ── 倉庫座標（與 Step 1 generator 一致）──────────────────────────────────────

LOCATION_COORDS: dict[str, tuple[float, float]] = {
    "高雄港物流中心":     (22.6023, 120.2965),
    "台北內湖倉":          (25.0693, 121.5755),
    "台中精密園區倉":     (24.1632, 120.6450),
    "桃園國際機場貨運站": (25.0797, 121.2321),
    "新竹科學園區倉":     (24.7882, 120.9980),
    "台南奇美物流倉":     (23.0398, 120.1724),
    "基隆港貨運站":       (25.1277, 121.7383),
    "宜蘭冷鏈倉":         (24.7521, 121.7583),
    "嘉義朴子倉":         (23.4618, 120.2449),
    "彰化和美倉":         (24.1030, 120.5363),
}

ROAD_FACTOR = 1.30   # 台灣公路距離 / 直線距離平均比


def _seed_from_id(waybill_id: str) -> int:
    return int(hashlib.md5(waybill_id.encode()).hexdigest()[:8], 16)


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def bezier_polyline(
    o_lat, o_lon, d_lat, d_lon,
    n: int = 14,
    rng: random.Random | None = None,
) -> list[list[float]]:
    """
    Quadratic Bezier 曲線，控制點偏移模擬高速公路彎道。
    n = 路徑點數（含起迄點）。
    """
    if rng is None:
        rng = random.Random()

    dlat = d_lat - o_lat
    dlon = d_lon - o_lon
    dist = math.sqrt(dlat ** 2 + dlon ** 2)

    if dist < 1e-5:
        return [[round(o_lat, 5), round(o_lon, 5)], [round(d_lat, 5), round(d_lon, 5)]]

    # 垂直方向單位向量
    perp_lat = -dlon / dist
    perp_lon =  dlat / dist

    # 控制點：中點往垂直方向偏移（偏移量含隨機擾動）
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


def mock_api_ts(date_iso: str | None) -> str:
    """模擬 API 呼叫時間戳：出貨日期當天早上 06–10 時之間。"""
    if not date_iso:
        date_iso = "2024-01-01"
    base = datetime.fromisoformat(date_iso).replace(
        hour=random.randint(6, 10),
        minute=random.randint(0, 59),
        second=random.randint(0, 59),
        tzinfo=timezone.utc,
    )
    return base.strftime("%Y-%m-%dT%H:%M:%SZ")


# ── 主流程 ────────────────────────────────────────────────────────────────────

def run():
    src = BASE / "output" / "cleaned_records.json"
    out = BASE / "output" / "routes_computed.json"

    with open(src, encoding="utf-8") as f:
        records: list[dict] = json.load(f)

    print(f"  讀取：{len(records)} 筆記錄")

    missing_location = 0
    for rec in records:
        origin = rec["origin"]
        dest   = rec["dest"]

        if origin not in LOCATION_COORDS or dest not in LOCATION_COORDS:
            rec["distanceKm"]  = None
            rec["coords"]      = []
            rec["apiTs"]       = None
            rec["routeSource"] = "ERROR_UNKNOWN_LOCATION"
            if "ERROR_ROUTE" not in rec["qualityFlags"]:
                rec["qualityFlags"].append("ERROR_ROUTE")
            rec["qualityLevel"] = "ERROR"
            missing_location += 1
            continue

        rng = random.Random(_seed_from_id(rec["id"]))

        o_lat, o_lon = LOCATION_COORDS[origin]
        d_lat, d_lon = LOCATION_COORDS[dest]

        straight_km  = haversine_km(o_lat, o_lon, d_lat, d_lon)
        road_km      = round(straight_km * ROAD_FACTOR)

        # 長途路線多幾個路徑點
        n_points = 14 if road_km > 100 else 10

        coords = bezier_polyline(o_lat, o_lon, d_lat, d_lon, n=n_points, rng=rng)

        rec["distanceKm"]  = road_km
        rec["coords"]      = coords
        rec["apiTs"]       = mock_api_ts(rec.get("date"))
        rec["routeSource"] = "MOCK_v1"

    with open(out, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"  輸出：{out}")
    if missing_location:
        print(f"  ⚠ 找不到座標的路線：{missing_location} 筆")


if __name__ == "__main__":
    run()
