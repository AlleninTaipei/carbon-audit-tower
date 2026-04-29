"""
Step 1 — 出貨部門原始資料模擬器
模擬 TMS (Transport Management System) 匯出的月度出貨 Excel，
刻意保留真實髒資料特徵，供後續 Step 2 ETL 清洗使用。
"""

import random
import datetime
import openpyxl
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, numbers
)
from openpyxl.utils import get_column_letter

random.seed(42)

# ── 基礎資料定義 ──────────────────────────────────────────────────────────────

CARRIERS = [
    "台灣大車隊物流", "嘉里大榮物流", "新竹物流", "統一速達",
    "黑貓宅急便", "大田物流", "宅配通",
]

VEHICLE_TYPES_RAW = [
    # 刻意混合：同一種車有多種寫法（真實髒資料）
    "大型貨車", "大型貨车", "大貨車",           # HGV >7.5t → 同一類
    "中型貨車", "中型货车", "3.5t-7.5t貨車",    # LGV 3.5–7.5t → 同一類
    "小型貨車",                                  # LGV <3.5t（邊緣案例）
]

# 起迄地對（address, lat, lon）
LOCATIONS = {
    "高雄港物流中心":   ("高雄市前鎮區成功二路1號",        22.6023, 120.2965),
    "台北內湖倉":        ("台北市內湖區堤頂大道二段400號",  25.0693, 121.5755),
    "台中精密園區倉":   ("台中市西屯區台灣大道三段99號",   24.1632, 120.6450),
    "桃園國際機場貨運站": ("桃園市大園區航站南路9號",       25.0797, 121.2321),
    "新竹科學園區倉":   ("新竹市東區光復路二段101號",      24.7882, 120.9980),
    "台南奇美物流倉":   ("台南市安南區工業二路11號",        23.0398, 120.1724),
    "基隆港貨運站":     ("基隆市中正區港西街23號",         25.1277, 121.7383),
    "宜蘭冷鏈倉":       ("宜蘭縣宜蘭市縣政北路1號",       24.7521, 121.7583),
    "嘉義朴子倉":       ("嘉義縣朴子市石棹里168號",        23.4618, 120.2449),
    "彰化和美倉":       ("彰化縣和美鎮道周路500號",        24.1030, 120.5363),
}

GOODS_TYPES = [
    "電子零組件", "半導體設備", "精密儀器", "包裝材料",
    "化工原料", "食品原料", "紡織品", "醫療器材", "汽車零件",
]

# ── 運單號生成 ────────────────────────────────────────────────────────────────

def gen_waybill(idx: int) -> str:
    prefixes = ["TW", "KH", "TC", "NT"]
    return f"{random.choice(prefixes)}-{2024:04d}-{idx:05d}"

# ── 髒資料注入策略 ────────────────────────────────────────────────────────────

def dirty_date(base_date: datetime.date) -> str:
    """日期欄位：混合多種格式（ETL 要辨識的痛點）"""
    formats = [
        "%Y/%m/%d",   # 2024/03/15  ← 最常見
        "%Y-%m-%d",   # 2024-03-15
        "%m/%d/%Y",   # 03/15/2024  ← 美式，偶爾出現
        "%Y.%m.%d",   # 2024.03.15
    ]
    if random.random() < 0.07:
        return ""     # 約 7% 遺漏（忘記填）
    return base_date.strftime(random.choice(formats))

def dirty_weight(weight_kg: float) -> str:
    """重量欄位：混合單位（kg vs 噸），偶爾帶單位文字"""
    r = random.random()
    if r < 0.05:
        return ""                           # 遺漏
    if r < 0.15:
        return f"{weight_kg / 1000:.2f}噸"  # 帶「噸」文字
    if r < 0.25:
        return f"{weight_kg:.0f}kg"         # 帶「kg」文字
    if r < 0.35:
        return str(round(weight_kg / 1000, 3))  # 用噸當單位但無標示（最難處理）
    return str(int(weight_kg))              # 正常 kg 數值

def dirty_vehicle(vtype: str) -> str:
    """車種：加入錯字、全形、縮寫等"""
    aliases = {
        "大型貨車": ["大型貨車", "大型貨车", "大貨車", "HGV", "大型", "10噸車"],
        "中型貨車": ["中型貨車", "中型货车", "3.5t-7.5t貨車", "LGV", "中型", "5噸車"],
        "小型貨車": ["小型貨車", "小貨車", "1噸車", "LGV-S"],
    }
    return random.choice(aliases.get(vtype, [vtype]))

# ── 主生成邏輯 ────────────────────────────────────────────────────────────────

def generate_records(n: int = 120) -> list[dict]:
    records = []
    location_names = list(LOCATIONS.keys())
    start_date = datetime.date(2024, 1, 2)

    for i in range(1, n + 1):
        origin_name = random.choice(location_names)
        dest_name = random.choice([l for l in location_names if l != origin_name])
        origin_addr, _, _ = LOCATIONS[origin_name]
        dest_addr, _, _ = LOCATIONS[dest_name]

        base_date = start_date + datetime.timedelta(days=random.randint(0, 364))
        weight_kg = random.randint(500, 18000)

        # 車種由重量推算（貼近真實邏輯）
        if weight_kg > 7500:
            canonical_vehicle = "大型貨車"
        elif weight_kg > 3500:
            canonical_vehicle = "中型貨車"
        else:
            canonical_vehicle = "小型貨車"

        carrier = random.choice(CARRIERS)
        # 車號：臺灣格式 + 偶爾格式錯誤
        plate_formats = [
            f"{random.choice('ABCDEFGHJKLMN')}{random.randint(10,99)}-{random.randint(100,999)}",
            f"{random.randint(100,999)}-{''.join(random.choices('ABCDEFGHJKLMN', k=2))}",
        ]
        plate = random.choice(plate_formats)
        if random.random() < 0.04:
            plate = ""   # 偶爾忘記填車號

        # 件數
        pieces = random.randint(1, 80)

        # 備註（偶爾填寫）
        notes_options = [
            "", "", "", "",   # 大多數空白
            "冷藏運輸", "易碎品", "危險品乙類", "需吊車卸貨",
            "客訴補送", "跨月結帳", "含稅", "含稅發票另補",
        ]
        note = random.choice(notes_options)

        # 距離：出貨部門不填（由 API 計算），約 20% 有自填
        driver_dist = ""
        if random.random() < 0.20:
            # 司機手填，可能不準確
            driver_dist = str(random.randint(30, 450))

        records.append({
            "運單號":       gen_waybill(i),
            "出貨日期":     dirty_date(base_date),
            "承運商":       carrier,
            "車號":         plate,
            "車種（原始）": dirty_vehicle(canonical_vehicle),
            "起點名稱":     origin_name,
            "起點地址":     origin_addr,
            "迄點名稱":     dest_name,
            "迄點地址":     dest_addr,
            "貨物類型":     random.choice(GOODS_TYPES),
            "件數":         pieces,
            "毛重(kg)_原始": dirty_weight(weight_kg),  # 髒欄位
            "司機自填距離(km)": driver_dist,           # 不可靠，待 API 覆蓋
            "備註":         note,
            # 以下為 ETL 填入欄位（出貨部門不填，留空）
            "標準化日期":   "",
            "標準化車種":   "",
            "標準化毛重(kg)": "",
            "API計算距離(km)": "",
            "載重(tonne)":  "",
            "碳排量(kg CO2e)": "",
            "資料品質旗標":    "",
        })

    return records

# ── Excel 輸出 ────────────────────────────────────────────────────────────────

HEADER_FILL    = PatternFill("solid", fgColor="1F4E79")
ETL_FILL       = PatternFill("solid", fgColor="E2EFDA")   # 淺綠：ETL 填入欄
DIRTY_FILL     = PatternFill("solid", fgColor="FFF2CC")   # 淺黃：髒資料欄
HEADER_FONT    = Font(bold=True, color="FFFFFF", size=10)
ETL_HEADER_FONT = Font(bold=True, color="375623", size=10)
DIRTY_FONT     = Font(bold=True, color="7F6000", size=10)
THIN           = Side(style="thin", color="BFBFBF")
BORDER         = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

# 欄寬設定
COL_WIDTHS = {
    "運單號": 18, "出貨日期": 15, "承運商": 14, "車號": 14,
    "車種（原始）": 16, "起點名稱": 18, "起點地址": 32,
    "迄點名稱": 18, "迄點地址": 32, "貨物類型": 12,
    "件數": 8, "毛重(kg)_原始": 16, "司機自填距離(km)": 18,
    "備註": 18,
    "標準化日期": 14, "標準化車種": 14, "標準化毛重(kg)": 16,
    "API計算距離(km)": 18, "載重(tonne)": 12,
    "碳排量(kg CO2e)": 18, "資料品質旗標": 16,
}

# 哪些欄是「髒資料欄」（黃底）/ ETL 欄（綠底）
DIRTY_COLS = {"毛重(kg)_原始", "車種（原始）", "司機自填距離(km)", "出貨日期"}
ETL_COLS   = {"標準化日期", "標準化車種", "標準化毛重(kg)",
              "API計算距離(km)", "載重(tonne)", "碳排量(kg CO2e)", "資料品質旗標"}


def write_excel(records: list[dict], output_path: str) -> None:
    wb = openpyxl.Workbook()

    # ── Sheet 1: 出貨明細 ──────────────────────────────────────────────────────
    ws = wb.active
    ws.title = "出貨明細"

    headers = list(records[0].keys())

    # 標題列
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.border = BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        if header in ETL_COLS:
            cell.fill = ETL_FILL
            cell.font = ETL_HEADER_FONT
        elif header in DIRTY_COLS:
            cell.fill = DIRTY_FILL
            cell.font = DIRTY_FONT
        else:
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT

    ws.row_dimensions[1].height = 32

    # 資料列
    for row_idx, record in enumerate(records, 2):
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=record[header])
            cell.border = BORDER
            cell.alignment = Alignment(vertical="center")
            if row_idx % 2 == 0:
                if header not in ETL_COLS and header not in DIRTY_COLS:
                    cell.fill = PatternFill("solid", fgColor="F5F5F5")

    # 欄寬
    for col_idx, header in enumerate(headers, 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = COL_WIDTHS.get(header, 14)

    # 凍結首列
    ws.freeze_panes = "A2"

    # ── Sheet 2: 圖例說明 ─────────────────────────────────────────────────────
    ws2 = wb.create_sheet("圖例與欄位說明")
    legend = [
        ["圖例", "說明"],
        ["■ 深藍底白字", "出貨部門原始填寫欄位（可信賴，但格式不統一）"],
        ["■ 淺黃底", "高髒資料風險欄位：格式不一、單位混用、偶有遺漏，ETL 必須處理"],
        ["■ 淺綠底", "ETL Pipeline 自動填入欄位：出貨部門不填，由系統計算後回寫"],
        ["", ""],
        ["欄位名稱", "說明", "ETL 處理重點"],
        ["運單號", "TMS 系統產生，格式：XX-YYYY-NNNNN", "—"],
        ["出貨日期", "【高髒資料】混合 4 種日期格式，7% 空白", "統一轉 ISO 8601"],
        ["承運商", "物流商名稱，已統一", "—"],
        ["車號", "車牌，偶爾空白（4%）", "空白視為未知"],
        ["車種（原始）", "【高髒資料】大型/中型/小型貨車有 6 種不同寫法", "對應至 HGV / LGV / LGV-S"],
        ["起點名稱 / 迄點名稱", "倉庫代稱，與內部 Master Data 對應", "地址標準化"],
        ["起點地址 / 迄點地址", "完整地址（供 Google TIM API 使用）", "—"],
        ["貨物類型", "商品分類", "—"],
        ["件數", "箱數", "—"],
        ["毛重(kg)_原始", "【高髒資料】混合 kg / 噸 / 文字單位，5% 空白", "統一轉 kg，再換算噸"],
        ["司機自填距離(km)", "司機手寫，80% 空白，不可靠", "僅供參考，以 API 距離為準"],
        ["備註", "自由文字", "—"],
        ["", "", ""],
        ["標準化日期", "【ETL 填入】統一 ISO 格式", ""],
        ["標準化車種", "【ETL 填入】HGV / LGV / LGV-S / UNKNOWN", ""],
        ["標準化毛重(kg)", "【ETL 填入】統一單位為 kg", ""],
        ["API計算距離(km)", "【ETL 填入】Google TIM API 回傳距離", ""],
        ["載重(tonne)", "【ETL 填入】毛重 ÷ 1000", ""],
        ["碳排量(kg CO2e)", "【ETL 填入】距離 × 載重 × 排放因子（DEFRA 2023）", ""],
        ["資料品質旗標", "【ETL 填入】OK / WARN_DATE / WARN_WEIGHT / WARN_VEHICLE / ERROR", ""],
    ]
    for r_idx, row in enumerate(legend, 1):
        for c_idx, val in enumerate(row, 1):
            cell = ws2.cell(row=r_idx, column=c_idx, value=val)
            cell.border = BORDER
            if r_idx == 1:
                cell.fill = HEADER_FILL
                cell.font = HEADER_FONT
            elif r_idx == 5:
                cell.fill = PatternFill("solid", fgColor="D9D9D9")
                cell.font = Font(bold=True, size=10)
            elif r_idx in (2, 3, 4):
                if c_idx == 1:
                    if "黃" in str(val):
                        cell.fill = DIRTY_FILL
                    elif "綠" in str(val):
                        cell.fill = ETL_FILL
                    elif "藍" in str(val):
                        cell.fill = HEADER_FILL
                        cell.font = HEADER_FONT

    ws2.column_dimensions["A"].width = 22
    ws2.column_dimensions["B"].width = 50
    ws2.column_dimensions["C"].width = 42

    # ── Sheet 3: 匯出摘要 ─────────────────────────────────────────────────────
    ws3 = wb.create_sheet("匯出摘要")
    summary_data = [
        ["匯出摘要", ""],
        ["匯出日期", datetime.date.today().strftime("%Y/%m/%d")],
        ["匯出單位", "出貨管理部"],
        ["資料區間", "2024/01/01 – 2024/12/31"],
        ["總運單數", len(records)],
        ["承運商數", len(CARRIERS)],
        ["涵蓋倉庫數", len(LOCATIONS)],
        ["", ""],
        ["注意事項", "本表為原始出貨資料，距離與碳排欄位由 ETL 系統自動回填"],
        ["排放因子來源", "DEFRA 2023"],
        ["計算方法", "GHG Protocol Scope 3 Category 4 Activity-based"],
    ]
    for r_idx, row in enumerate(summary_data, 1):
        for c_idx, val in enumerate(row, 1):
            cell = ws3.cell(row=r_idx, column=c_idx, value=val)
            cell.border = BORDER
            if r_idx == 1:
                cell.fill = HEADER_FILL
                cell.font = HEADER_FONT
    ws3.column_dimensions["A"].width = 20
    ws3.column_dimensions["B"].width = 50

    wb.save(output_path)
    print(f"✅ 已產生：{output_path}")
    print(f"   運單數：{len(records)} 筆")
    print(f"   工作表：出貨明細 / 圖例與欄位說明 / 匯出摘要")


# ── 執行 ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    os.makedirs("raw_data", exist_ok=True)
    records = generate_records(n=120)
    output = "raw_data/shipping_2024_raw.xlsx"
    write_excel(records, output)
