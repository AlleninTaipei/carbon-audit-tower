# Carbon Audit Control Tower

GHG Protocol Scope 3 · Category 4 Upstream Transportation 查驗介面 PoC

> 以「動態數位軌跡」取代「靜態截圖存證」——當稽核員點選任一筆碳排紀錄，系統即時在地圖上渲染該趟行程的實際路徑，並顯示完整的審計軌跡資訊（API 時間戳、排放因子版本、計算公式）。

---

## 專案結構

```
digitalesg/
├── audit-control-tower.html   # 查驗介面主體（不含任何金鑰）
├── server.js                  # 輕量伺服器，負責注入 API Key
├── .env                       # API Key 存放處（不進 git）
├── .gitignore
└── README.md
```

---

## 快速啟動

### 1. 確認 `.env` 已填入金鑰

```
GOOGLE_MAPS_API_KEY=AIzaSy...你的金鑰...
```

### 2. 啟動伺服器

```bash
# Node.js >= 20.6（內建 --env-file，無需 npm install）
node --env-file=.env server.js

# Node.js < 20.6
GOOGLE_MAPS_API_KEY=AIzaSy... node server.js
```

### 3. 開啟瀏覽器

```
http://localhost:3000
```

---

## 功能說明

| 功能 | 說明 |
|:-|:-|
| 碳排紀錄表格 | 10 筆台灣真實物流路線的 Mock 資料，含運單號、車種、日期、距離、載重、碳排量 |
| 點擊即渲染路徑 | 點選任一列，右側地圖即時繪製行程 Polyline，並標示起點（S）與終點（E） |
| 自動縮放 | 地圖自動 fit bounds 至選取的路徑範圍 |
| 審計軌跡資訊列 | 顯示 API 回傳時間戳、排放因子版本、計算方法、路徑點數 |
| 摘要統計卡片 | 總碳排量、資料筆數、平均每趟碳排，顯示於頁首 |

---

## Mock 資料說明

排放因子來源：**DEFRA 2023**

| 車種 | 排放因子 |
|:-|:-|
| 大型貨車（HGV >7.5t） | 0.150 kg CO₂e / tonne-km |
| 中型貨車（LGV 3.5–7.5t） | 0.300 kg CO₂e / tonne-km |

計算公式：`距離(km) × 載重(tonne) × 排放因子 = 碳排量(kg CO₂e)`

涵蓋路線：高雄港↔台北、台中↔台北（國道1號）、台北↔宜蘭（國道5號）、台北↔基隆、台南↔高雄、新竹↔台中、桃園↔新竹科學園區 等。

---

## 安全設計

API Key **永遠不出現在任何原始碼或版本歷史中**。

```
.env  →  server.js（執行時注入）  →  瀏覽器
```

- `.env` 已列入 `.gitignore`，不會被 git 追蹤
- `audit-control-tower.html` 僅含 `YOUR_API_KEY` 佔位符
- 伺服器啟動時若 Key 未設定，立即報錯退出

建議在 [Google Cloud Console](https://console.cloud.google.com) 為此 Key 額外設定 **HTTP referrer 限制**（僅允許 `localhost:3000`），作為雙重保護。

---

## 技術背景

本 PoC 對應 plan.md 所規劃的「互動式查核控制台（Audit Control Tower）」，旨在演示以下稽核邏輯：

- **完整性**：系統化儲存 100% 路徑資料（Polyline），比人工抽樣截圖更完整
- **真實性**：資料庫直連顯示，排除人工編輯或修圖偽造的可能
- **標準化**：符合 ISAE 3410 對數位證據的要求，以數據標記取代影像檔作為第三方查驗佐證
