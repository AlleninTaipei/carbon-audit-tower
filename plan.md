# 建構的 GHG Protocol Scope 3 交通運輸碳審計基礎設施

>「為了符合 ISAE 3410（碳排放報告保證標準）對數據完整性與自動化控制的要求，我們建立的是 API-based 直接取證機制。單筆截圖無法避免人工編輯的風險，而我們保留的 Polyline 數位軌跡與 Timestamp 原始回傳數據，能提供更高的審計強度與數據可回溯性。」

* 以下摘要關鍵元件與做法，以技術先進性（Digital Evidence）取代傳統低效的人工要求：

## 核心技術元件 (Technical Stack)

|元件|角色與功能|關鍵產出|
|:-|:-|:-|
|Google TIM API|計算引擎|獲取符合 GHG Protocol 的活動基礎（Activity-based）高精度碳排數據|
|BigQuery|數據中樞|儲存原始活動資料（如 GPS、運單）與計算結果，建立不可篡改的審計軌跡|
|GEOGRAPHY (WKT/GeoJSON)|空間數據格式|將 API 回傳的 Polyline 轉為地理座標字串，作為路徑的「數位指紋」|
|Looker Studio|查驗界面|建立動態儀表板，將數據視覺化，供稽核員進行「穿透式」查核。|

## 核心做法與策略 (Implementation Strategy)

### 1. 從「靜態存證」轉向「動態驗證」

* 做法： 不再儲存數萬張地圖截圖，而是儲存路徑的 經緯度座標串（Polyline）。
* 效益： 節省儲存成本，且數據可檢索、可排序，比圖片更具透明度。

### 2. 建立「自動化審計軌跡 (Audit Trail)」

* 做法： 在 BigQuery 中完整保留 API 請求與回傳的原始 JSON 紀錄（包含時間戳、使用的排放因子版本、計算邏輯）。
* 效益： 證明數據從採集到計算完全自動化，無人工干預風險（Anti-tampering）。

### 3. 開發「互動式查核控制台 (Audit Control Tower)」

* 做法： 在 Looker Studio 設置「跨圖表篩選」。當稽核員選中任一筆碳排紀錄，右側 Google Maps 視窗即時渲染出該趟行程的實際軌跡。
* 效益： 滿足稽核員對視覺證據的需求，同時大幅提升查驗效率與專業感。

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
