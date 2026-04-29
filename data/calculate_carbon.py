"""
Step 4 — 碳排計算 + Audit Trail 產生
Input : output/routes_computed.json
Output: output/carbon_audit_records.json   ← Control Tower 吃這個
        output/audit_trail.jsonl           ← BigQuery 模擬（newline-delimited JSON）

計算公式（GHG Protocol Scope 3 Activity-based）：
  碳排量(kg CO₂e) = 距離(km) × 載重(tonne) × 排放因子(kg CO₂e/tonne-km)

排放因子來源：DEFRA 2023
  HGV  (>7.5t)      : 0.150 kg CO₂e/tonne-km  → v1.4
  LGV  (3.5-7.5t)   : 0.300 kg CO₂e/tonne-km  → v1.2
  LGV-S(<3.5t)      : 0.467 kg CO₂e/tonne-km  → v1.1
  UNKNOWN            : 0.300 kg CO₂e/tonne-km  → v1.2（保守估計）
"""

import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent

EMISSION_FACTORS: dict[str, dict] = {
    "HGV":     {"ef": 0.150, "version": "DEFRA 2023 v1.4"},
    "LGV":     {"ef": 0.300, "version": "DEFRA 2023 v1.2"},
    "LGV-S":   {"ef": 0.467, "version": "DEFRA 2023 v1.1"},
    "UNKNOWN": {"ef": 0.300, "version": "DEFRA 2023 v1.2"},
}


def run():
    src = BASE / "output" / "routes_computed.json"
    out_ct   = BASE / "output" / "carbon_audit_records.json"
    out_bq   = BASE / "output" / "audit_trail.jsonl"

    with open(src, encoding="utf-8") as f:
        records: list[dict] = json.load(f)

    print(f"  讀取：{len(records)} 筆記錄")

    pipeline_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ct_records  = []
    bq_lines    = []

    total_co2 = 0.0
    no_co2_count = 0

    for rec in records:
        vehicle_code = rec.get("vehicleCode", "UNKNOWN")
        ef_info  = EMISSION_FACTORS[vehicle_code]
        ef_val   = ef_info["ef"]
        ef_ver   = ef_info["version"]

        dist     = rec.get("distanceKm")
        weight   = rec.get("weight")      # tonne

        flags = list(rec.get("qualityFlags", ["OK"]))

        # 計算碳排
        if dist is not None and weight is not None and weight > 0:
            co2 = round(dist * weight * ef_val, 2)
            total_co2 += co2
        else:
            co2 = None
            if "ERROR_NO_CO2" not in flags:
                flags.append("ERROR_NO_CO2")
            no_co2_count += 1

        # 更新 qualityLevel
        if any(f.startswith("ERROR") for f in flags):
            q_level = "ERROR"
        elif any(f.startswith("WARN") for f in flags):
            q_level = "WARN"
        else:
            q_level = "OK"

        # ── Control Tower record ───────────────────────────────────────────
        ct = {
            # 識別 & 顯示
            "id":           rec["id"],
            "date":         rec.get("date") or "—",
            "dateRaw":      rec.get("dateRaw", ""),
            "carrier":      rec.get("carrier", ""),
            "plate":        rec.get("plate", ""),
            # 車種
            "vehicle":      rec.get("vehicle", "unknown"),
            "vehicleLabel": rec.get("vehicleLabel", "未知"),
            "vehicleRaw":   rec.get("vehicleRaw", ""),
            # 路線
            "origin":       rec["origin"],
            "originAddr":   rec.get("originAddr", ""),
            "dest":         rec["dest"],
            "destAddr":     rec.get("destAddr", ""),
            # 貨物
            "goodsType":    rec.get("goodsType", ""),
            "pieces":       rec.get("pieces", 0),
            # 量值
            "distance":     dist,
            "weight":       weight,
            "weightKg":     rec.get("weightKg"),
            "weightRaw":    rec.get("weightRaw", ""),
            "driverDist":   rec.get("driverDist", ""),
            # 碳排
            "co2":          co2,
            "ef":           ef_val,
            "efVersion":    ef_ver,
            # 路徑
            "coords":       rec.get("coords", []),
            "apiTs":        rec.get("apiTs", ""),
            "routeSource":  rec.get("routeSource", ""),
            # 備註 & 品質
            "note":         rec.get("note", ""),
            "qualityFlags": flags,
            "qualityLevel": q_level,
        }
        ct_records.append(ct)

        # ── BigQuery / Audit Trail 行 ──────────────────────────────────────
        bq = {
            "schema_version": "1.0",
            "waybill":        rec["id"],
            "date":           rec.get("date"),
            "carrier":        rec.get("carrier"),
            "origin":         rec["origin"],
            "dest":           rec["dest"],
            "vehicle_type":   vehicle_code,
            "vehicle_raw":    rec.get("vehicleRaw"),
            "weight_tonne":   weight,
            "weight_kg_raw":  rec.get("weightRaw"),
            "distance_km":    dist,
            "driver_dist_km": rec.get("driverDist") or None,
            "emission_factor": ef_val,
            "ef_version":     ef_ver,
            "co2_kg":         co2,
            "route_source":   rec.get("routeSource"),
            "api_ts":         rec.get("apiTs"),
            "pipeline_run_ts": pipeline_ts,
            "quality_flags":  flags,
            "quality_level":  q_level,
        }
        bq_lines.append(json.dumps(bq, ensure_ascii=False))

    # ── 寫出 ──────────────────────────────────────────────────────────────
    out_ct.parent.mkdir(parents=True, exist_ok=True)
    with open(out_ct, "w", encoding="utf-8") as f:
        json.dump(ct_records, f, ensure_ascii=False, indent=2)

    with open(out_bq, "w", encoding="utf-8") as f:
        f.write("\n".join(bq_lines) + "\n")

    ok   = sum(1 for r in ct_records if r["qualityLevel"] == "OK")
    warn = sum(1 for r in ct_records if r["qualityLevel"] == "WARN")
    err  = sum(1 for r in ct_records if r["qualityLevel"] == "ERROR")

    print(f"  輸出：{out_ct}")
    print(f"  輸出：{out_bq}")
    print(f"  品質：OK={ok}  WARN={warn}  ERROR={err}")
    print(f"  總碳排：{total_co2:,.1f} kg CO₂e（{no_co2_count} 筆無法計算）")


if __name__ == "__main__":
    run()
