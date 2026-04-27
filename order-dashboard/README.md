# 訂單分析互動式儀表板

基於 Streamlit + Plotly 的訂單分析儀表板,讀取 Excel 訂單匯出檔,提供會員、產品、時間、年齡等多維度分析。

## 功能總覽

| 分頁 | 內容 |
|------|------|
| **總覽** | KPI(總營收/訂單/會員/AOV/回購率)、營收趨勢(日/週/月)、新客 vs 老客 |
| **會員分析** | 整體回購率、回購次數分佈、首購到第二次間隔、RFM 分群、Cohort 留存熱力圖 |
| **產品分析** | Top 20 排行(銷量/金額)、產品復購率、連帶購買 Top 10、分類佔比 |
| **時間分析** | 24 小時熱度、星期分佈、月份/季節、時段 × 星期熱力圖 |
| **會員輪廓** | 年齡/性別/地區分佈、各年齡層客單價、各年齡層偏好分類 |

每個圖表下方都有「下載 CSV」按鈕。

## 安裝

需要 Python 3.10+。

```bash
# 1. 安裝相依套件
pip install -r requirements.txt

# 2.(可選)產生範例資料,共 100 張訂單
python sample_data/generate_sample.py
```

## 啟動

### Mac 一鍵啟動(推薦)

在 Finder 中**雙擊 `start.command`** 即可。

- 第一次會自動建立虛擬環境 + 安裝套件(約 1-2 分鐘),後續每次啟動約 3 秒。
- 啟動後瀏覽器會自動打開 `http://localhost:8501`。
- 要關閉:回到開啟的終端機視窗按 `Control + C`,或直接關掉視窗。
- 若雙擊出現「無法打開,因為來自未識別的開發者」:**右鍵 → 打開**(只需第一次)。
- 需要 Mac 上有 Python 3.10+。若沒有,腳本會提示你前往 [python.org](https://www.python.org/downloads/) 下載。

### 手動啟動(進階使用者)

```bash
streamlit run app.py
```

預設網址:`http://localhost:8501`。從側邊欄上傳 Excel,或勾選「使用範例資料」即可開始。

## Excel 欄位對照表

程式會自動將以下欄名對應到內部標準欄位。**找不到的欄位會以空值填入並顯示警告,不會中斷程式。**

| 標準欄位 | 接受的中/英文欄名 | 必要性 |
|---|---|---|
| `order_id` | 訂單編號 / 訂單ID / order_no / order_id | 必要 |
| `order_date` | 訂單日期 / 下單時間 / 建立時間 / order_date / created_at | 必要 |
| `order_status` | 訂單狀態 / 狀態 / status | 必要 |
| `order_amount` | 訂單金額 / 訂單總額 / 總金額 / amount / total | 建議(若缺,會以小計加總補) |
| `member_id` | 會員ID / 會員編號 / 客戶ID / member_id / customer_id | 建議(若缺,會以 email + phone 組合) |
| `member_name` | 會員姓名 / 姓名 / 客戶姓名 / name | 選用 |
| `birth_year` | 出生年 / 出生年份 / birth_year / year_of_birth | 選用(用於年齡計算) |
| `gender` | 性別 / gender | 選用 |
| `region` | 地區 / 縣市 / region / city | 選用 |
| `email` | Email / 信箱 / 電子郵件 | 選用 |
| `phone` | 電話 / 手機 / phone / mobile | 選用 |
| `sku` | 產品SKU / SKU / 商品編號 | 必要(復購率以 SKU 為主鍵) |
| `product_name` | 產品名稱 / 商品名稱 / product_name | 必要 |
| `product_category` | 產品分類 / 商品分類 / category | 建議 |
| `unit_price` | 單價 / unit_price / price | 建議 |
| `quantity` | 數量 / quantity / qty | 建議 |
| `subtotal` | 小計 / subtotal / line_total | 建議(若缺,會以 unit_price × quantity 補) |

訂單狀態會被正規化為三類:**已完成 / 已取消 / 退貨**(辨識常見中英文寫法,如 `completed`、`paid`、`cancelled`、`refunded` 等)。

## 指標定義

| 指標 | 定義 |
|---|---|
| 回購率 | 篩選區間內購買 ≥ 2 張不同訂單的會員 / 總會員(預設排除最近 30 天才首購的會員,可在側邊欄調整) |
| 產品復購率 | 該產品被同一會員購買 ≥ 2 張不同訂單的會員數 / 該產品所有購買會員數 |
| 新客 | 在所有資料中,該訂單為該會員的首張訂單 |
| 老客 | 在所有資料中,該會員之前已有訂單 |
| 沉睡客戶 | 最後一筆訂單距今 ≥ 90 天(可調) |
| 流失客戶 | 最後一筆訂單距今 ≥ 180 天(可調) |
| 客單價 (AOV) | 區間內總營收 / 區間內訂單數,儀表板同時顯示中位數 |
| LTV | 該會員所有訂單金額總和(顯示在 RFM 表的 monetary 欄) |

### RFM 分群規則

R/F/M 各自以分位數計算 1-5 分(R 越小、F/M 越大者得 5 分),再依下列規則分群:

| 條件 | 分群 |
|---|---|
| R ≥ 4 且 F ≥ 4 且 M ≥ 4 | **VIP** |
| F ≥ 4 且 M ≥ 3(其他條件不符) | **忠實客戶** |
| R ≥ 4 且 F ≤ 2 | **潛力客戶**(最近活躍但購買次數少) |
| R ≤ 2 且 F ≥ 3 | **沉睡客戶**(過去常買但很久沒買) |
| R ≤ 2(其他條件不符) | **流失客戶** |
| 其他 | **一般客戶** |

## 已處理的常見問題

1. **同一天多次下單**:回購以「不同訂單編號」計,而非以日期計。
2. **平均值受極端值影響**:總覽 KPI 與各年齡層客單價同時顯示中位數。
3. **新會員剛註冊還沒時間回購**:預設排除最近 30 天才首購的會員(可在側邊欄調整)。
4. **產品復購粒度**:預設以 SKU 為主鍵,在「產品分析」分頁可切換為「商品名稱」。
5. **退貨/取消訂單**:預設排除,可在側邊欄打開來檢視。
6. **欄位名稱差異**:支援中英文常見寫法,缺欄不會崩潰,僅顯示警告。
7. **時區**:所有時間轉為 Asia/Taipei,避免跨時區 Excel 造成日期偏移。
8. **空值**:年齡/地區/性別空值標記為「未知」,不刪除訂單。

## 隱私處理

- 預設遮罩會員姓名(王*明)、Email(a***@gmail.com)、電話(091****56)。
- 側邊欄提供「顯示完整個資」切換鈕,**僅供本地使用時開啟**;對外簡報請維持遮罩。
- 程式只在本地讀取資料,不上傳到任何外部服務。

## 專案結構

```
order-dashboard/
├── app.py                    # Streamlit 主程式
├── data_loader.py            # 讀取與清理 Excel
├── metrics/
│   ├── member.py             # 回購率、RFM、Cohort、會員分群
│   ├── product.py            # 產品排行、復購率、連帶購買
│   ├── time_analysis.py      # 時間維度分析
│   └── demographics.py       # 年齡 / 性別 / 地區分佈
├── components/
│   ├── filters.py            # 側邊欄篩選器、PII 遮罩
│   └── charts.py             # 共用 Plotly 圖表 + 下載 CSV
├── sample_data/
│   ├── generate_sample.py    # 範例資料產生器
│   └── orders_sample.xlsx    # 範例資料(100 張訂單)
├── requirements.txt
└── README.md
```

## 客製化建議

- 若你的欄位名稱無法被自動辨識,在 `data_loader.py` 的 `COLUMN_ALIASES` 加入別名即可。
- 若要調整年齡分桶,修改 `data_loader.py` 的 `AGE_BINS` / `AGE_LABELS`。
- 若要支援不同貨幣,改 `components/charts.py` 的 `fmt_currency`。
- 若要新增分頁,在 `app.py` 的 `tabs = st.tabs([...])` 加一項並寫一個 `page_xxx` 函式即可。
