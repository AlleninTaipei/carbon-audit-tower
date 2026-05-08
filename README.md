# Carbon Audit Control Tower

GHG Protocol Scope 3 · Category 4 Upstream Transportation · 端對端稽核流程 PoC

> 完整模擬從「出貨部門提交原始 Excel」到「稽核員在 Audit Control Tower 查驗碳排路徑」的全流程，以動態數位軌跡取代靜態截圖存證，符合 ISAE 3410 對數位審計軌跡的要求。

---

## 架構總覽

```
出貨部門                  ETL Pipeline                    Control Tower / BigQuery
──────────            ──────────────────────            ──────────────────────────
shipping_2024   →  Step 2  Step 3  Step 4   →   carbon_audit_records.json
_raw.xlsx          清洗     路線    碳排           audit_trail.jsonl
(120 筆)           標準化   計算    計算                 │          │
                                               server.js 注入   upload_to_bq.py
                                                     │                │
                                              localhost:3000     BigQuery
                                            互動式查核控制台    ghg_scope3_cat4
```

---

## 專案結構

```
carbon-audit-tower/
├── data/
│   ├── generate_shipping_data.py   # Step 1 — 出貨部門 Excel 模擬器
│   ├── etl_clean.py                # Step 2 — 資料清洗 + 品質旗標
│   ├── compute_routes.py           # Step 3 — 路線計算 orchestrator（讀 ROUTE_PROVIDER）
│   ├── route_providers/
│   │   ├── mock_provider.py        # Bezier Polyline + Haversine（預設，可離線）
│   │   └── routes_provider.py      # Google Routes API v2（需啟用 Routes API）
│   ├── calculate_carbon.py         # Step 4 — DEFRA 2023 碳排計算 + Audit Trail
│   ├── upload_to_bq.py             # Step 5 — 上傳至 BigQuery（兩張表）
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
├── .env                            # API Key + Pipeline 環境變數（不進 git）
└── .gitignore
```

---

## 快速啟動

### 前置需求

- Python 3.11+（含 `openpyxl`、`requests`）
- Node.js 20.6+
- Google Cloud 專案，並建立以下兩把 API Key（詳見下方「設定環境變數」）：
  - `GOOGLE_MAPS_API_KEY`：開啟 **Maps JavaScript API**，設 HTTP referrer 限制
  - `GOOGLE_ROUTES_API_KEY`：開啟 **Routes API**，不設 referrer 限制（僅 `ROUTE_PROVIDER=routes` 時需要）

### 1. 安裝 Python 依賴

```bash
pip3 install openpyxl requests
```

### 2. 設定環境變數

建立 `.env`（不進 git）：

```bash
# .env

# 瀏覽器端地圖渲染（Maps JavaScript API）
# 用途：server.js 啟動時注入 HTML，供 Control Tower 在瀏覽器中繪製路徑地圖
# 限制：建議設定 HTTP referrer 限制，只允許 localhost 或指定網域
GOOGLE_MAPS_API_KEY=AIzaSy...你的金鑰...

# 伺服器端路線計算（Routes API v2）
# 用途：pipeline 執行時呼叫 Google Routes API 取得真實公路距離與 Polyline
# 限制：不可設定 HTTP referrer 限制（Python 呼叫沒有 Referer header）；
#       建議 API restrictions 只勾選 Routes API
# 僅在 ROUTE_PROVIDER=routes 時需要
GOOGLE_ROUTES_API_KEY=AIzaSy...另一把金鑰...

# 路線計算供應商切換
# mock   — Bezier Polyline + Haversine 估算，可離線，適合開發與展示
# routes — Google Routes API v2，真實公路距離與軌跡，需啟用 Routes API
ROUTE_PROVIDER=mock
```

#### 為什麼需要兩把 Key？

| | `GOOGLE_MAPS_API_KEY` | `GOOGLE_ROUTES_API_KEY` |
|:--|:--|:--|
| **呼叫端** | 瀏覽器（Maps JavaScript API） | Python 伺服器（Routes API v2）|
| **有無 Referer header** | 有（來自網頁網域） | 無（server-side 呼叫）|
| **建議 Application restriction** | HTTP referrers（限定網域） | None 或 IP addresses |
| **建議 API restriction** | Maps JavaScript API | Routes API |

瀏覽器用的 Key 若沒有 HTTP referrer 限制，任何人拿到 Key 都可以在自己的網站消耗你的配額；伺服器用的 Key 若設了 referrer 限制，Python 呼叫因沒有 Referer header 會被 Google 擋下（403）。兩把分開才能同時滿足兩端的安全需求。

#### 兩把 Key 的觸發時機

| 時機 | 使用的 Key | 條件 |
|:--|:--|:--|
| `python3 data/run_pipeline.py` | `GOOGLE_ROUTES_API_KEY` | 僅當 `ROUTE_PROVIDER=routes` |
| 瀏覽器點擊運單（Control Tower） | `GOOGLE_MAPS_API_KEY` | 永遠，與 `ROUTE_PROVIDER` 無關 |

`GOOGLE_ROUTES_API_KEY` 只在 pipeline 執行期間被用到，執行完畢即結束。`GOOGLE_MAPS_API_KEY` 則只要 Control Tower 開著、使用者點擊運單，就持續被呼叫，與 pipeline 採用哪個 provider 無關。

`ROUTE_PROVIDER` 決定座標的「來源品質」（Bezier 估算 vs 真實路網），`GOOGLE_MAPS_API_KEY` 負責把這些座標「畫出來」，兩者分工明確、互不影響。

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

#### 車種代碼（`vehicleCode`）

ETL 將原始資料中 6 種不同寫法（含簡體字、英文縮寫、噸位標記）統一對應至以下三個標準代碼，後續碳排計算與 Control Tower 顯示均以此為準：

| 代碼 | 全名 | 噸位 |
|:--|:--|:--|
| **HGV** | Heavy Goods Vehicle | > 7.5 t |
| **LGV** | Light Goods Vehicle | 3.5 – 7.5 t |
| **LGV-S** | Light Goods Vehicle – Small | < 3.5 t |

#### 資料品質旗標（`qualityLevel` / `qualityFlags`）

| 旗標 | 層級 | 說明 |
|:--|:--|:--|
| **OK** | record | 所有欄位乾淨，無需修正 |
| **WARN** | record | 至少一個欄位被自動修正，整筆標為警告（黃色左邊框） |
| **WARN_DATE** | field | 日期格式非標準，ETL 已自動解析 |
| **WARN_WEIGHT** | field | 重量單位不明確，已依啟發式規則換算 |
| **WARN_VEHICLE** | field | 車種寫法非標準，已自動對應 |
| **ERROR** | record | 無法修正，該筆被排除，不計入碳排 |

`qualityLevel` 的判定邏輯：`qualityFlags` 中只要有任何一個 `WARN_*`，整筆 `qualityLevel` 即設為 `WARN`；有 `ERROR_*` 則設為 `ERROR`。

### Step 3 — 路線計算 (`compute_routes.py`)

`compute_routes.py` 為 orchestrator，讀取 `ROUTE_PROVIDER` 環境變數後將計算委派給對應的 provider：

| `ROUTE_PROVIDER` | Provider | 路徑點數 | 說明 |
|:--|:--|:--|:--|
| `mock`（預設） | `route_providers/mock_provider.py` | 10–14 點 | Quadratic Bezier 曲線 + Haversine × 1.30 道路係數；可離線執行 |
| `routes` | `route_providers/routes_provider.py` | 1,000–2,000 點 | Google Routes API v2；真實公路距離與路網軌跡；需啟用 Routes API |

兩個 provider 對外介面一致，均回傳 `distanceKm`、`coords`、`apiTs`、`routeSource`（`MOCK_v1` 或 `ROUTES_API_v2`）。

#### 視覺差異與審計意義

切換 provider 後，Control Tower 地圖的路徑渲染會有明顯不同：

- **mock**：A → B 之間呈現一條平滑拋物線弧（14 個點），不跟著道路走
- **routes**：路線沿台灣實際公路彎折（1,000–2,000 個點），可看到國道交流道、省道轉彎

從審計角度，真實路網軌跡（`ROUTES_API_v2`）提供的是可逐段核對的行車路徑，而非估算弧線，符合 ISAE 3410 對數位取證的要求。`routeSource` 欄位會記錄在 `audit_trail.jsonl`，稽核員可查知每筆碳排的路徑資料來源。

Mock provider 涵蓋 10 個物流節點：高雄港、台北內湖、台中精密園區、桃園機場、新竹科學園區、台南奇美、基隆港、宜蘭冷鏈倉、嘉義朴子、彰化和美。Waybill ID 作為隨機種子，確保每次輸出可重現。

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

## `audit_trail.jsonl` 說明

### 格式：JSON Lines（NDJSON）

一行 = 一筆完整 JSON 物件，行與行之間沒有逗號、沒有外層陣列。

```json
{
  "schema_version": "1.0",
  "waybill":        "TW-2024-00001",
  "vehicle_raw":    "大型貨车",          // 原始髒資料（保留）
  "vehicle_type":   "HGV",              // ETL 標準化後
  "weight_kg_raw":  "8524",             // 原始重量字串
  "weight_tonne":   8.524,              // 換算後的值
  "emission_factor": 0.15,              // 實際使用的排放因子數值
  "ef_version":     "DEFRA 2023 v1.4",  // 排放因子版本
  "co2_kg":         505.05,             // 最終計算結果
  "api_ts":         "2024-05-21T06:01:58Z",   // 路線 API 呼叫時間戳
  "pipeline_run_ts":"2026-04-29T01:56:53Z",   // 本次 Pipeline 執行時間
  "quality_flags":  ["OK"],
  "quality_level":  "OK"
}
```

對比 `carbon_audit_records.json`（供 Control Tower 渲染的顯示用陣列），`.jsonl` 的優勢：

| | `.json`（陣列） | `.jsonl`（每行一筆）|
|:--|:--|:--|
| 讀入方式 | 必須一次載入整個檔案 | 可逐行串流讀取 |
| 追加新資料 | 要修改整個檔案結構 | 直接 `append` 一行 |
| 大數據處理 | 記憶體壓力大 | Spark / BigQuery 原生支援 |
| 損毀容忍 | 一個語法錯誤 → 整個檔案失效 | 壞掉的行可以跳過 |

### 核心用途：不可篡改的計算紀錄

每一行保存「當下那次計算的完整快照」。稽核員若質疑某筆碳排數字，可在此查到完整的輸入 → 公式 → 輸出，且 `pipeline_run_ts` 證明數字由自動化產生、非事後手改。

### 使用場景

**場景 1 — 匯入 BigQuery**

使用 `data/upload_to_bq.py` 腳本（見下方「BigQuery 整合」章節），一行指令將兩張表完整上傳，無需手動 `bq load`。

**場景 2 — 跨年度 / 跨排放因子版本比較**

每筆紀錄帶有 `pipeline_run_ts` 與 `ef_version`。當 DEFRA 更新排放因子時，重跑 Pipeline 後 append 新批次，即可用同一張 BigQuery 表比較同一批運單在不同版本下的碳排差異。

**場景 3 — 稽核員要求原始計算依據**

ISAE 3410 查核時，直接交付此檔案（或從 BigQuery 匯出 CSV），完整說明每筆的排放因子版本、原始輸入值與計算過程，滿足數位審計軌跡的舉證要求。

### 在本 PoC 中的位置

```
Pipeline → audit_trail.jsonl   ← 目前：本地檔案模擬
                ↓
         BigQuery Table         ← 真實環境：一行 bq load 指令即可銜接
                ↓
         Looker Studio / Control Tower
```

---

## BigQuery 整合

### 已建立的資源

| 資源 | 詳細 |
|:--|:--|
| Dataset | `ghg_scope3_cat4`（asia-east1，台灣區）|
| `carbon_records` | 120 筆、28 欄，含 **GEOGRAPHY** 路徑（WKT LINESTRING，2,039 點）|
| `audit_trail` | 120 筆、20 欄，不可篡改審計軌跡 |

### 上傳步驟

```bash
# 1. 安裝 Python 套件
pip3 install google-cloud-bigquery

# 2. 驗證（開啟瀏覽器登入 Google 帳號）
gcloud auth application-default login

# 3. 上傳（WRITE_TRUNCATE：重跑會覆寫，不累加）
python3 data/upload_to_bq.py --project YOUR_PROJECT_ID
```

---

### 資料品質演示（稽核員視角）

BigQuery 讓「資料是否可信」從口頭說明變成可執行的 SQL 查詢。以下六個問題是稽核員最常問的，每個問題對應一條查詢：

**Q1 — 整批資料的品質全貌是什麼？**

```sql
SELECT quality_level,
       COUNT(*)             AS cnt,
       ROUND(SUM(co2_kg),1) AS total_co2_kg
FROM `YOUR_PROJECT.ghg_scope3_cat4.carbon_records`
GROUP BY quality_level
ORDER BY cnt DESC;
```

> 預期結果：OK=98（81.7%）、WARN=19、ERROR=3。ERROR 的 `co2_kg` 為 NULL，已排除於總碳排之外。

---

**Q2 — 資料問題的具體類型是什麼？**

```sql
SELECT flag,
       COUNT(*) AS affected_records
FROM `YOUR_PROJECT.ghg_scope3_cat4.carbon_records`,
  UNNEST(quality_flags) AS flag
WHERE flag != 'OK'
GROUP BY flag
ORDER BY affected_records DESC;
```

> `quality_flags` 是 BigQuery REPEATED STRING 欄位，可直接 UNNEST 展開，無需解析 JSON 字串。

---

**Q3 — 哪些運單有問題、為什麼？**

```sql
SELECT id, date, carrier, origin, dest,
       quality_flags,
       co2_kg
FROM `YOUR_PROJECT.ghg_scope3_cat4.carbon_records`
WHERE quality_level IN ('WARN', 'ERROR')
ORDER BY quality_level, id;
```

> WARN 筆數仍有 `co2_kg`（ETL 自動修正後計算），ERROR 筆數 `co2_kg` 為 NULL（缺少必要欄位，無法計算）。

---

**Q4 — 排放因子版本是否全批一致？**

```sql
SELECT ef_version,
       COUNT(*)             AS cnt,
       ROUND(SUM(co2_kg),1) AS total_co2_kg
FROM `YOUR_PROJECT.ghg_scope3_cat4.carbon_records`
GROUP BY ef_version;
```

> 全部 120 筆均應為 `DEFRA 2023 v1.4`，證明計算標準一致，無版本混用。

---

**Q5 — 計算是自動化執行的，還是人工輸入的？**

```sql
SELECT
  MIN(pipeline_run_ts)          AS pipeline_start,
  MAX(pipeline_run_ts)          AS pipeline_end,
  COUNT(DISTINCT pipeline_run_ts) AS distinct_run_batches,
  COUNT(*)                      AS total_records
FROM `YOUR_PROJECT.ghg_scope3_cat4.audit_trail`;
```

> `distinct_run_batches = 1` 代表全部 120 筆來自同一次 Pipeline 執行，非事後逐筆手輸。`pipeline_run_ts` 即為 Anti-tampering 時間戳。

---

**Q6 — 距離數字可以獨立核算嗎？**

```sql
SELECT id, carrier,
       distance_km                              AS pipeline_km,
       ROUND(ST_Length(route_polyline)/1000, 1) AS geography_km,
       ABS(distance_km - ST_Length(route_polyline)/1000) AS diff_km
FROM `YOUR_PROJECT.ghg_scope3_cat4.carbon_records`
ORDER BY diff_km DESC
LIMIT 10;
```

> `route_polyline` 是 GEOGRAPHY 型別，`ST_Length()` 直接計算球面距離（公尺）。可與 `distance_km`（Pipeline 計算值）互相驗算，差異來自球面距離 vs 道路係數（×1.30）。

---

### 稽核員話術

| 稽核員問 | 對應查詢 | 回答邏輯 |
|:--|:--|:--|
| 這批資料可信嗎？ | Q1 | 81.7% 乾淨，問題類型全部可列舉 |
| 品質問題是什麼？ | Q2 + Q3 | 日期格式、重量單位——系統自動標記，非人工判斷 |
| 排放因子版本正確嗎？ | Q4 | 全批 DEFRA 2023 v1.4，無混版 |
| 數字是手動填的嗎？ | Q5 | 同一批次 Pipeline 自動產出，timestamp 可查 |
| 距離可以核對嗎？ | Q6 | GEOGRAPHY 空間計算獨立驗算，非黑箱 |

---

## Control Tower 功能

| 功能 | 說明 |
|:--|:--|
| 年度摘要統計 | 總碳排量、HGV / LGV 分組碳排、資料品質概覽（OK/WARN/ERROR 計數） |
| 多維篩選 | 車種 · 承運商 · 資料品質 · 排序（碳排量/日期/距離） |
| 即時搜尋 | 依運單號、路線名稱、承運商搜尋 |
| 品質視覺標記 | WARN → 黃色左邊框；ERROR → 紅色左邊框；Polyline 顏色同步 |
| 點擊渲染路徑 | 選取任一運單，地圖即時繪製路徑（`mock`：Bezier 弧線；`routes`：真實路網軌跡），S/E 標記起迄點 |
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
