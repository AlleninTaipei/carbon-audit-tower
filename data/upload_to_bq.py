"""
Upload carbon audit pipeline data to BigQuery.

Usage:
    pip3 install google-cloud-bigquery
    gcloud auth application-default login
    python3 data/upload_to_bq.py --project YOUR_GCP_PROJECT_ID

Tables created in dataset `ghg_scope3_cat4`:
    carbon_records  — 120 筆碳排記錄（含 GEOGRAPHY 路徑）
    audit_trail     — 不可篡改審計軌跡
"""

import argparse
import json
from pathlib import Path

from google.cloud import bigquery

BASE = Path(__file__).parent
OUTPUT = BASE / "output"

DATASET_ID = "ghg_scope3_cat4"
DATASET_LOCATION = "asia-east1"

CARBON_RECORDS_SCHEMA = [
    bigquery.SchemaField("id",             "STRING"),
    bigquery.SchemaField("date",           "DATE"),
    bigquery.SchemaField("date_raw",       "STRING"),
    bigquery.SchemaField("carrier",        "STRING"),
    bigquery.SchemaField("plate",          "STRING"),
    bigquery.SchemaField("vehicle",        "STRING"),
    bigquery.SchemaField("vehicle_label",  "STRING"),
    bigquery.SchemaField("vehicle_raw",    "STRING"),
    bigquery.SchemaField("origin",         "STRING"),
    bigquery.SchemaField("origin_addr",    "STRING"),
    bigquery.SchemaField("dest",           "STRING"),
    bigquery.SchemaField("dest_addr",      "STRING"),
    bigquery.SchemaField("goods_type",     "STRING"),
    bigquery.SchemaField("pieces",         "INTEGER"),
    bigquery.SchemaField("distance_km",    "FLOAT"),
    bigquery.SchemaField("weight_tonne",   "FLOAT"),
    bigquery.SchemaField("weight_kg",      "INTEGER"),
    bigquery.SchemaField("weight_raw",     "STRING"),
    bigquery.SchemaField("driver_dist_km", "FLOAT"),
    bigquery.SchemaField("co2_kg",         "FLOAT"),
    bigquery.SchemaField("ef",             "FLOAT"),
    bigquery.SchemaField("ef_version",     "STRING"),
    bigquery.SchemaField("route_polyline", "GEOGRAPHY"),
    bigquery.SchemaField("route_source",   "STRING"),
    bigquery.SchemaField("api_ts",         "TIMESTAMP"),
    bigquery.SchemaField("quality_flags",  "STRING", mode="REPEATED"),
    bigquery.SchemaField("quality_level",  "STRING"),
    bigquery.SchemaField("note",           "STRING"),
]

AUDIT_TRAIL_SCHEMA = [
    bigquery.SchemaField("schema_version",  "STRING"),
    bigquery.SchemaField("waybill",         "STRING"),
    bigquery.SchemaField("date",            "DATE"),
    bigquery.SchemaField("carrier",         "STRING"),
    bigquery.SchemaField("origin",          "STRING"),
    bigquery.SchemaField("dest",            "STRING"),
    bigquery.SchemaField("vehicle_type",    "STRING"),
    bigquery.SchemaField("vehicle_raw",     "STRING"),
    bigquery.SchemaField("weight_tonne",    "FLOAT"),
    bigquery.SchemaField("weight_kg_raw",   "STRING"),
    bigquery.SchemaField("distance_km",     "INTEGER"),
    bigquery.SchemaField("driver_dist_km",  "FLOAT"),
    bigquery.SchemaField("emission_factor", "FLOAT"),
    bigquery.SchemaField("ef_version",      "STRING"),
    bigquery.SchemaField("co2_kg",          "FLOAT"),
    bigquery.SchemaField("route_source",    "STRING"),
    bigquery.SchemaField("api_ts",          "TIMESTAMP"),
    bigquery.SchemaField("pipeline_run_ts", "TIMESTAMP"),
    bigquery.SchemaField("quality_flags",   "STRING", mode="REPEATED"),
    bigquery.SchemaField("quality_level",   "STRING"),
]


def coords_to_wkt(coords: list) -> str | None:
    """Convert [[lat, lon], ...] to WKT LINESTRING(lon lat, ...) for BigQuery GEOGRAPHY."""
    if not coords or len(coords) < 2:
        return None
    points = ", ".join(f"{lon} {lat}" for lat, lon in coords)
    return f"LINESTRING({points})"


def _str_or_none(v) -> str | None:
    s = str(v).strip() if v is not None else ""
    return s or None


def _valid_date(v) -> str | None:
    """Return ISO date string if valid (starts with 20xx), else None."""
    s = str(v).strip() if v else ""
    return s if s.startswith("20") else None


def transform_carbon_record(r: dict) -> dict:
    driver_raw = r.get("driverDist", "")
    driver_km = float(driver_raw) if str(driver_raw).strip() else None

    return {
        "id":             r["id"],
        "date":           _valid_date(r.get("date")),
        "date_raw":       _str_or_none(r.get("dateRaw")),
        "carrier":        _str_or_none(r.get("carrier")),
        "plate":          _str_or_none(r.get("plate")),
        "vehicle":        _str_or_none(r.get("vehicle")),
        "vehicle_label":  _str_or_none(r.get("vehicleLabel")),
        "vehicle_raw":    _str_or_none(r.get("vehicleRaw")),
        "origin":         _str_or_none(r.get("origin")),
        "origin_addr":    _str_or_none(r.get("originAddr")),
        "dest":           _str_or_none(r.get("dest")),
        "dest_addr":      _str_or_none(r.get("destAddr")),
        "goods_type":     _str_or_none(r.get("goodsType")),
        "pieces":         r.get("pieces"),
        "distance_km":    r.get("distance"),
        "weight_tonne":   r.get("weight"),
        "weight_kg":      r.get("weightKg"),
        "weight_raw":     _str_or_none(r.get("weightRaw")),
        "driver_dist_km": driver_km,
        "co2_kg":         r.get("co2"),
        "ef":             r.get("ef"),
        "ef_version":     _str_or_none(r.get("efVersion")),
        "route_polyline": coords_to_wkt(r.get("coords", [])),
        "route_source":   _str_or_none(r.get("routeSource")),
        "api_ts":         r.get("apiTs") or None,
        "quality_flags":  r.get("qualityFlags") or [],
        "quality_level":  _str_or_none(r.get("qualityLevel")),
        "note":           _str_or_none(r.get("note")),
    }


def transform_audit_record(r: dict) -> dict:
    return {
        "schema_version":  r.get("schema_version"),
        "waybill":         r.get("waybill"),
        "date":            r.get("date"),
        "carrier":         _str_or_none(r.get("carrier")),
        "origin":          _str_or_none(r.get("origin")),
        "dest":            _str_or_none(r.get("dest")),
        "vehicle_type":    _str_or_none(r.get("vehicle_type")),
        "vehicle_raw":     _str_or_none(r.get("vehicle_raw")),
        "weight_tonne":    r.get("weight_tonne"),
        "weight_kg_raw":   _str_or_none(r.get("weight_kg_raw")),
        "distance_km":     r.get("distance_km"),
        "driver_dist_km":  r.get("driver_dist_km"),
        "emission_factor": r.get("emission_factor"),
        "ef_version":      _str_or_none(r.get("ef_version")),
        "co2_kg":          r.get("co2_kg"),
        "route_source":    _str_or_none(r.get("route_source")),
        "api_ts":          r.get("api_ts") or None,
        "pipeline_run_ts": r.get("pipeline_run_ts") or None,
        "quality_flags":   r.get("quality_flags") or [],
        "quality_level":   _str_or_none(r.get("quality_level")),
    }


def ensure_dataset(client: bigquery.Client, project: str) -> None:
    dataset_ref = bigquery.DatasetReference(project, DATASET_ID)
    try:
        client.get_dataset(dataset_ref)
        print(f"  Dataset exists: {project}.{DATASET_ID}")
    except Exception:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = DATASET_LOCATION
        client.create_dataset(dataset)
        print(f"  Created dataset: {project}.{DATASET_ID} (location: {DATASET_LOCATION})")


def load_table(
    client: bigquery.Client,
    project: str,
    table_id: str,
    rows: list,
    schema: list,
) -> None:
    table_ref = f"{project}.{DATASET_ID}.{table_id}"
    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    )
    job = client.load_table_from_json(rows, table_ref, job_config=job_config)
    job.result()
    table = client.get_table(table_ref)
    print(f"  Loaded {table.num_rows} rows → {table_ref}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload carbon audit data to BigQuery")
    parser.add_argument("--project", required=True, help="GCP project ID")
    args = parser.parse_args()

    client = bigquery.Client(project=args.project)
    print(f"BigQuery client ready  (project: {args.project})\n")

    ensure_dataset(client, args.project)

    print("\n[1/2] carbon_records ...")
    raw = json.loads((OUTPUT / "carbon_audit_records.json").read_text(encoding="utf-8"))
    carbon_rows = [transform_carbon_record(r) for r in raw]
    load_table(client, args.project, "carbon_records", carbon_rows, CARBON_RECORDS_SCHEMA)

    print("\n[2/2] audit_trail ...")
    audit_rows = []
    for line in (OUTPUT / "audit_trail.jsonl").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            audit_rows.append(transform_audit_record(json.loads(line)))
    load_table(client, args.project, "audit_trail", audit_rows, AUDIT_TRAIL_SCHEMA)

    print(f"""
Done!
  {args.project}.{DATASET_ID}.carbon_records  ({len(carbon_rows)} rows)
  {args.project}.{DATASET_ID}.audit_trail     ({len(audit_rows)} rows)
""")


if __name__ == "__main__":
    main()
