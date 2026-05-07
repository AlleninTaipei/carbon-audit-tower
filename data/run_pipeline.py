"""
Pipeline 編排器 — 依序執行 Step 2 → Step 3 → Step 4
執行方式：python3 data/run_pipeline.py

從專案根目錄的 .env 載入環境變數，子行程自動繼承（支援 ROUTE_PROVIDER 等設定）。
"""

import os
import subprocess
import sys
from pathlib import Path

BASE     = Path(__file__).parent
ENV_FILE = BASE.parent / ".env"

STEPS = [
    ("Step 2  ETL 清洗",              "etl_clean.py"),
    ("Step 3  路線計算",               "compute_routes.py"),
    ("Step 4  碳排計算 + Audit Trail", "calculate_carbon.py"),
]


def _load_env(path: Path) -> None:
    """將 .env 檔的 KEY=VALUE 載入 os.environ（已設定的 OS 變數優先）。"""
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            val = val.split("#")[0].strip()   # 去掉行尾註解
            key = key.strip()
            if key and key not in os.environ:  # OS 環境變數優先
                os.environ[key] = val


def run():
    _load_env(ENV_FILE)

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
