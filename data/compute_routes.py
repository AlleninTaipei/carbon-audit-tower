"""
Step 3 — 路線計算
Input : output/cleaned_records.json
Output: output/routes_computed.json

路線計算供應商由環境變數 ROUTE_PROVIDER 控制（預設 mock）：
  ROUTE_PROVIDER=mock    Quadratic Bezier + Haversine（本地，可離線）
  ROUTE_PROVIDER=routes  Google Routes API v2（需啟用 Routes API）
"""

import hashlib
import json
import os
import random
from pathlib import Path

BASE     = Path(__file__).parent
ENV_FILE = BASE.parent / ".env"


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            val = val.split("#")[0].strip()
            key = key.strip()
            if key:
                os.environ[key] = val  # 直接覆寫，確保 .env 優先


_load_env(ENV_FILE)

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


def _seed_from_id(waybill_id: str) -> int:
    return int(hashlib.md5(waybill_id.encode()).hexdigest()[:8], 16)


def _load_provider(name: str):
    if name == "routes":
        from route_providers import routes_provider as provider
    else:
        from route_providers import mock_provider as provider
    return provider


def run():
    provider_name = os.getenv("ROUTE_PROVIDER", "mock").lower()
    provider = _load_provider(provider_name)
    print(f"  路線供應商：{provider_name.upper()}")

    src = BASE / "output" / "cleaned_records.json"
    out = BASE / "output" / "routes_computed.json"

    with open(src, encoding="utf-8") as f:
        records: list[dict] = json.load(f)

    print(f"  讀取：{len(records)} 筆記錄")

    missing_location = 0
    for rec in records:
        origin_name = rec["origin"]
        dest_name   = rec["dest"]

        if origin_name not in LOCATION_COORDS or dest_name not in LOCATION_COORDS:
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
        result = provider.compute_route(
            origin=LOCATION_COORDS[origin_name],
            dest=LOCATION_COORDS[dest_name],
            waybill_id=rec["id"],
            date=rec.get("date"),
            rng=rng,
        )
        rec.update(result)

    with open(out, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"  輸出：{out}")
    if missing_location:
        print(f"  ⚠ 找不到座標的路線：{missing_location} 筆")


if __name__ == "__main__":
    run()
