# 建構的 GHG Protocol Scope 3 交通運輸碳審計基礎設施

>「為了符合 ISAE 3410（碳排放報告保證標準）對數據完整性與自動化控制的要求，我們建立的是 API-based 直接取證機制。單筆截圖無法避免人工編輯的風險，而我們保留的 Polyline 數位軌跡與 Timestamp 原始回傳數據，能提供更高的審計強度與數據可回溯性。」

* 以下摘要關鍵元件與做法，以技術先進性（Digital Evidence）取代傳統低效的人工要求：

## 核心技術元件 (Technical Stack)

|元件|角色與功能|關鍵產出|現況|
|:-|:-|:-|:-|
|Google Routes API v2|路線計算引擎|取得真實公路距離與 1,000–2,000 點路網 Polyline，作為 Activity-based 碳排計算依據|✅ 已對接|
|DEFRA 2023 排放因子|碳排計算標準|HGV / LGV / LGV-S 三級排放因子，套用公式計算 kg CO₂e|✅ 已實作|
|GEOGRAPHY (WKT/GeoJSON)|空間數據格式|將 API 回傳的 Polyline 轉為地理座標字串，作為路徑的「數位指紋」|✅ 已實作|
|自建 HTML Control Tower|查驗界面（PoC）|互動式稽核控制台，地圖即時渲染真實路網軌跡，供稽核員穿透查核|✅ 已上線|
|BigQuery|數據中樞（目標）|儲存原始活動資料與計算結果，建立不可篡改的審計軌跡；`audit_trail.jsonl` 已相容格式|✅ 已串接|
|Looker Studio|管理決策層（目標）|不取代 Control Tower，而是在其上建立管理儀表板：回答「在哪裡改善」與「策略是否奏效」|🔲 待串接|

## 核心做法與策略 (Implementation Strategy)

### 1. 從「靜態存證」轉向「動態驗證」

* 做法： 不再儲存數萬張地圖截圖，而是儲存路徑的 經緯度座標串（Polyline）。
* 效益： 節省儲存成本，且數據可檢索、可排序，比圖片更具透明度。

### 2. 建立「自動化審計軌跡 (Audit Trail)」

* 做法： 在 BigQuery 中完整保留 API 請求與回傳的原始 JSON 紀錄（包含時間戳、使用的排放因子版本、計算邏輯）。
* 效益： 證明數據從採集到計算完全自動化，無人工干預風險（Anti-tampering）。

### 3. 開發「互動式查核控制台 (Audit Control Tower)」

* 做法： 當稽核員選中任一筆碳排紀錄，右側 Google Maps 視窗即時渲染出該趟行程的實際軌跡。
* 效益： 滿足稽核員對視覺證據的需求，同時大幅提升查驗效率與專業感。
* **現況（PoC）：** 已以自建 HTML + Node.js 實現，搭配 Google Routes API 可渲染 1,000–2,000 點的真實路網軌跡（非估算弧線）。長期目標為遷移至 Looker Studio。

### 專業應對邏輯 (The "Why")

* 若稽核員堅持要求截圖，您可以從以下三點專業立場進行溝通：
  * 完整性 (Completeness)： 系統化存儲 100% 的路徑數據（Polyline），比人工抽樣截圖更完整。
  * 真實性 (Data Integrity)： 資料庫直連顯示，排除了人工編輯或修圖偽造的可能性。
  * 標準化 (Standardization)： 符合國際數位審計趨勢，利用「數據標記」而非「影像檔」作為第三方查驗的佐證資料。

## 開發 20260429

Step 1 完成。 產出：data/raw_data/shipping_2024_raw.xlsx，120 筆運單，3 個工作表。

腳本設計重點

|髒資料特徵|比例|用途|
|:-|:-|:-|
|日期 4 種格式混用（含美式、點分）|100%|測試 ETL 日期解析|
|日期空白|~7%|測試遺漏值處理|
|車種 6 種寫法（含簡體、英文縮寫）|100%|測試正規化對應表|
|重量混合 kg/噸/文字|~25%|測試單位換算|
|車號空白|~4%|測試 nullable 欄位|
|司機自填距離（80% 空白）|20%|凸顯 API 距離的必要性|

預判下一步 (Step 2–4)

Step 2 — ETL 清洗腳本 (etl_clean.py)：讀取 Excel → 解析各格式日期 → 車種正規化對應表 → 重量單位統一 → 打上資料品質旗標（OK / WARN / ERROR）。

Step 3 — 距離計算 (compute_distance.py)：對每筆運單呼叫 Google Distance Matrix API（或用預設距離 mock）取得公里數，回寫 Excel。

Step 4 — 碳排計算 + Audit Trail (calculate_carbon.py)：套用 DEFRA 2023 排放因子，產生 JSON audit trail（含 timestamp、factor version、計算公式），模擬 BigQuery 寫入。

---

## 架構決策：Route Provider 抽象層（20260507）

### 決策

於 Step 3 引入 **provider 抽象層**，以環境變數 `ROUTE_PROVIDER` 控制路線計算供應商，mock 與 Google Routes API 兩條路徑並存。

> 補充說明：原計畫中提到的「Google TIM API」實為 **Travel Impact Model API**，其功能僅限於航班碳排計算，無法用於公路貨運。公路運輸路徑與距離的真實資料來源應改用 **Google Routes API v2**，碳排計算繼續沿用 DEFRA 2023 排放因子。

### 結構

```
data/
  compute_routes.py            ← orchestrator：讀 env var，委派給 provider
  route_providers/
    mock_provider.py           ← Bezier Polyline + Haversine（現行邏輯，可離線）
    routes_provider.py         ← Google Routes API v2（已實作）
```

### 設計原則

- **介面契約**：兩個 provider 均實作相同簽名 `compute_route(origin, dest, waybill_id, date, rng) → dict`，回傳 `distanceKm`、`coords`、`apiTs`、`routeSource`。
- **下游透明**：Step 4（碳排計算）只讀 `distanceKm`，不感知資料來源，切換 provider 不需改任何其他腳本。
- **Data Lineage**：`routeSource` 欄位（`MOCK_v1` / `ROUTES_API_v2`）在 `audit_trail.jsonl` 中留存，稽核員可查知每筆碳排的路徑資料來源。
- **切換方式**：`.env` 將 `ROUTE_PROVIDER` 改為 `routes`，執行 `python3 data/run_pipeline.py` 即可。

### Google Routes API 啟用步驟

1. 前往 Google Cloud Console → APIs & Services → Library，搜尋 **Routes API** → 啟用
2. 建立一把 **server-side 專用 API Key**（`GOOGLE_ROUTES_API_KEY`）：
   - Application restrictions：**None**（Python 呼叫沒有 HTTP Referer，設 referrer 限制會導致 403）
   - API restrictions：勾選 **Routes API**（限縮用途）
3. 原有的 `GOOGLE_MAPS_API_KEY` 保留給瀏覽器端地圖渲染（Maps JavaScript API），建議維持 HTTP referrer 限制
4. 在 `.env` 加入 `GOOGLE_ROUTES_API_KEY=...` 並將 `ROUTE_PROVIDER` 改為 `routes`
5. 安裝 Python 依賴：`pip3 install requests`

> **為什麼要兩把 Key？** 瀏覽器呼叫有 Referer header，可設 referrer 限制保護配額；Python 伺服器端呼叫無 Referer，若 Key 設了 referrer 限制，Google 會回 403 Forbidden。兩把分開才能同時滿足兩端的安全需求。
