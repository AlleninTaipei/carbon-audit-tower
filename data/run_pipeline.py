"""
Pipeline 編排器 — 依序執行 Step 2 → Step 3 → Step 4
執行方式：python3 data/run_pipeline.py
"""

import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent
STEPS = [
    ("Step 2  ETL 清洗",              "etl_clean.py"),
    ("Step 3  路線計算 (Mock)",        "compute_routes.py"),
    ("Step 4  碳排計算 + Audit Trail", "calculate_carbon.py"),
]


def run():
    print("\n" + "═" * 60)
    print("  GHG Scope 3 Cat.4 Carbon Audit Pipeline")
    print("═" * 60)

    for name, script in STEPS:
        print(f"\n▶ {name}")
        result = subprocess.run(
            [sys.executable, BASE / script],
            cwd=BASE,
        )
        if result.returncode != 0:
            print(f"\n❌ {name} 失敗，Pipeline 中止")
            sys.exit(1)

    print("\n" + "═" * 60)
    print("  ✅  Pipeline 完成")
    print("  →   data/output/carbon_audit_records.json")
    print("  →   data/output/audit_trail.jsonl")
    print("  →   啟動 Control Tower：node --env-file=.env server.js")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    run()
