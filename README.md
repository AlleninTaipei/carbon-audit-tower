# Carbon Audit Control Tower

GHG Protocol Scope 3 · Category 4 Upstream Transportation · 端對端稽核流程 PoC

> 完整模擬從「出貨部門提交原始 Excel」到「稽核員在 Audit Control Tower 查驗碳排路徑」的全流程，以動態數位軌跡取代靜態截圖存證，符合 ISAE 3410 對數位審計軌跡的要求。

---

## 架構總覽

```
出貨部門                  ETL Pipeline                    Control Tower
──────────            ──────────────────────            ──────────────────
shipping_2024   →  Step 2  Step 3  Step 4   →   carbon_audit_records.json
_raw.xlsx          清洗     路線    碳排                       │
(120 筆)           標準化   計算    計算                 server.js 注入
                                                         │
                                                    localhost:3000
                                                  互動式查核控制台
```

---

## 專案結構

```
carbon-audit-tower/
├── data/
│   ├── generate_shipping_data.py   # Step 1 — 出貨部門 Excel 模擬器
│   ├── etl_clean.py                # Step 2 — 資料清洗 + 品質旗標
│   ├── compute_routes.py           # Step 3 — 路線距離 + Polyline 計算
│   ├── calculate_carbon.py         # Step 4 — DEFRA 2023 碳排計算 + Audit Trail
│   ├── run_pipeline.py             # Pipeline 編排器（Step 2→3→4）
│   ├── raw_data/
│   │   └── shipping_2024_raw.xlsx  # Step 1 產出（含設計髒資料）
│   └── output/
│       ├── cleaned_records.json    # Step 2 產出
│       ├── routes_computed.json    # Step 3 產出
│       ├── carbon_audit_records.json  # Step 4 產出 ← Control Tower 資料源
│       └── audit_trail.jsonl       # BigQuery 模擬（newline-delimited JSON）
├── audit-control-tower.html        # 查驗介面（__PIPELINE_DATA__ 佔位符）
├── server.js                       # 注入 API Key + Pipeline 資料後供瀏覽器
├── plan.md                         # 技術策略文件
├── .env                            # API Key（不進 git）
└── .gitignore
```

---

## 快速啟動

### 前置需求

- Python 3.11+（含 `openpyxl`）
- Node.js 20.6+
- Google Maps API Key（開啟 Maps JavaScript API）

### 1. 安裝 Python 依賴

```bash
pip3 install openpyxl
```

### 2. 設定 API Key

```bash
# .env
GOOGLE_MAPS_API_KEY=AIzaSy...你的金鑰...
```

### 3. 執行 Pipeline（Step 1 已預先產出，執行 Step 2–4）

```bash
python3 data/run_pipeline.py
```

輸出：

```
════════════════════════════════════════
  GHG Scope 3 Cat.4 Carbon Audit Pipeline
════════════════════════════════════════
▶ Step 2  ETL 清洗
▶ Step 3  路線計算 (Mock)
▶ Step 4  碳排計算 + Audit Trail
  ✅  Pipeline 完成
  →   data/output/carbon_audit_records.json
  →   data/output/audit_trail.jsonl
```

### 4. 啟動 Control Tower

```bash
# Node.js >= 20.6
node --env-file=.env server.js

# Node.js < 20.6
GOOGLE_MAPS_API_KEY=AIzaSy... node server.js
```

### 5. 開啟瀏覽器

```
http://localhost:3000
```

---

## Pipeline 說明

### Step 1 — 出貨部門 Excel 模擬 (`generate_shipping_data.py`)

產出 120 筆 2024 年度運單，刻意注入真實髒資料特徵供後續 ETL 清洗：

| 欄位 | 髒資料特徵 | 比例 |
|:--|:--|:--|
| 出貨日期 | 4 種格式混用（`YYYY/MM/DD`、`YYYY-MM-DD`、`MM/DD/YYYY`、`YYYY.MM.DD`） | 100% |
| 出貨日期 | 遺漏（忘記填） | ~7% |
| 車種 | 6 種不同寫法（含簡體字、英文縮寫） | 100% |
| 毛重 | 混合 kg / 噸 / 帶單位文字 | ~25% |
| 毛重 | 遺漏 | ~5% |
| 司機自填距離 | 80% 空白，不可靠 | — |

工作表：`出貨明細` / `圖例與欄位說明` / `匯出摘要`

### Step 2 — ETL 清洗 (`etl_clean.py`)

| 清洗項目 | 邏輯 |
|:--|:--|
| 日期標準化 | 嘗試 4 種格式解析 → ISO 8601；失敗 → `WARN_DATE` |
| 車種標準化 | 對應表（6 種寫法 → `HGV` / `LGV` / `LGV-S`）；未知 → `WARN_VEHICLE` |
| 重量標準化 | 自動識別 kg / 噸 / 文字單位 → 統一 kg；遺漏 → `WARN_WEIGHT` |
| 資料品質旗標 | `OK` / `WARN_*` / `ERROR_*` per record |

2024 全年結果：OK=98 · WARN=22 · ERROR=0

### Step 3 — 路線計算 (`compute_routes.py`)

使用 **Quadratic Bezier 曲線**模擬 Polyline（14 個座標點），距離採 Haversine × 1.30 道路係數（台灣公路平均值）。Waybill ID 作為隨機種子，確保每次輸出可重現。

涵蓋 10 個物流節點：高雄港、台北內湖、台中精密園區、桃園機場、新竹科學園區、台南奇美、基隆港、宜蘭冷鏈倉、嘉義朴子、彰化和美。

> 換接真實 Google Directions / TIM API 時，僅需替換此步驟。

### Step 4 — 碳排計算 (`calculate_carbon.py`)

排放因子來源：**DEFRA 2023**

| 車種 | 排放因子 | 版本 |
|:--|:--|:--|
| 大型貨車（HGV >7.5t） | 0.150 kg CO₂e / tonne-km | DEFRA 2023 v1.4 |
| 中型貨車（LGV 3.5–7.5t） | 0.300 kg CO₂e / tonne-km | DEFRA 2023 v1.2 |
| 小型貨車（LGV <3.5t） | 0.467 kg CO₂e / tonne-km | DEFRA 2023 v1.1 |

計算公式：`距離(km) × 載重(tonne) × 排放因子 = 碳排量(kg CO₂e)`

同步產出 `audit_trail.jsonl`，每行一筆 JSON，格式相容 BigQuery 直接匯入。

2024 全年結果：**總碳排 39,875 kg CO₂e**（3 筆因重量缺失無法計算）

---

## Control Tower 功能

| 功能 | 說明 |
|:--|:--|
| 年度摘要統計 | 總碳排量、HGV / LGV 分組碳排、資料品質概覽（OK/WARN/ERROR 計數） |
| 多維篩選 | 車種 · 承運商 · 資料品質 · 排序（碳排量/日期/距離） |
| 即時搜尋 | 依運單號、路線名稱、承運商搜尋 |
| 品質視覺標記 | WARN → 黃色左邊框；ERROR → 紅色左邊框；Polyline 顏色同步 |
| 點擊渲染路徑 | 選取任一運單，地圖即時繪製 Bezier Polyline，S/E 標記起迄點 |
| 審計軌跡詳情 | 顯示原始值 vs 標準化值、計算式分解、品質旗標說明、API 時間戳 |

---

## 安全設計

API Key **永遠不出現在任何原始碼或版本歷史中**。

```
.env  →  server.js（執行時注入）  →  瀏覽器（__PIPELINE_DATA__ 同步注入）
```

- `.env` 已列入 `.gitignore`
- `audit-control-tower.html` 僅含 `YOUR_API_KEY` 與 `__PIPELINE_DATA__` 佔位符
- 伺服器啟動時若 Key 或 Pipeline 資料缺失，立即報錯退出

---

## 稽核立場說明

> 「本系統以 API-based 直接取證機制取代傳統截圖存證。保留的 Polyline 數位軌跡與 Timestamp 原始回傳數據，提供更高審計強度與資料可回溯性，符合 ISAE 3410 對數據完整性與自動化控制的要求。」

| 稽核原則 | 實現方式 |
|:--|:--|
| **完整性** | 100% 運單系統化儲存，無人工抽樣 |
| **真實性** | Pipeline 全自動計算，無人工干預風險（Anti-tampering） |
| **可回溯性** | `audit_trail.jsonl` 保留排放因子版本、計算時間戳、原始輸入值 |
| **標準化** | 符合 GHG Protocol Scope 3 Activity-based 計算方法 |
