"""讀取與清理訂單 Excel 資料。

本模組負責將使用者上傳的 Excel 檔解析為標準化的 DataFrame,並做基本的
資料清理(時區、年齡計算、空值、訂單狀態正規化等)。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

import pandas as pd
import pytz

DEFAULT_TZ = "Asia/Taipei"

STANDARD_COLUMNS = [
    "order_id",
    "order_date",
    "order_status",
    "order_amount",
    "member_id",
    "member_name",
    "birth_year",
    "gender",
    "region",
    "email",
    "phone",
    "sku",
    "product_name",
    "product_category",
    "unit_price",
    "quantity",
    "subtotal",
]

COLUMN_ALIASES: dict[str, list[str]] = {
    "order_id": ["訂單編號", "訂單ID", "order_no", "order id", "order_id", "orderid"],
    "order_date": ["訂單日期", "下單時間", "建立時間", "order_date", "created_at", "date"],
    "order_status": ["訂單狀態", "狀態", "status", "order_status"],
    "order_amount": ["訂單金額", "訂單總額", "總金額", "amount", "total"],
    "member_id": ["會員ID", "會員編號", "客戶ID", "member_id", "customer_id", "user_id"],
    "member_name": ["會員姓名", "姓名", "客戶姓名", "name", "member_name"],
    "birth_year": ["出生年", "出生年份", "birth_year", "year_of_birth"],
    "gender": ["性別", "gender", "sex"],
    "region": ["地區", "縣市", "region", "city", "area"],
    "email": ["Email", "email", "信箱", "電子郵件"],
    "phone": ["電話", "手機", "phone", "mobile"],
    "sku": ["產品SKU", "SKU", "sku", "商品編號"],
    "product_name": ["產品名稱", "商品名稱", "product_name", "item_name"],
    "product_category": ["產品分類", "商品分類", "category", "product_category"],
    "unit_price": ["單價", "unit_price", "price"],
    "quantity": ["數量", "quantity", "qty"],
    "subtotal": ["小計", "subtotal", "line_total"],
}

COMPLETED_STATUS = {"已完成", "完成", "completed", "complete", "paid", "已付款", "成立"}
CANCELLED_STATUS = {"已取消", "取消", "cancelled", "canceled", "void"}
REFUNDED_STATUS = {"退貨", "退款", "refunded", "returned"}

AGE_BINS = [0, 18, 25, 35, 45, 55, 200]
AGE_LABELS = ["18 以下", "18-24", "25-34", "35-44", "45-54", "55+"]


@dataclass
class LoadResult:
    """資料載入結果。

    attributes:
        df: 訂單明細(每列一個訂單行項目)
        orders: 訂單層級彙總(每列一張訂單)
        warnings: 載入過程的警告訊息(欄位缺失等)
    """

    df: pd.DataFrame
    orders: pd.DataFrame
    warnings: list[str]


def _normalize_header(name: str) -> str:
    return str(name).strip().lower().replace(" ", "").replace("_", "")


def _build_alias_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for std, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            lookup[_normalize_header(alias)] = std
    return lookup


def map_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """將原始欄位名稱對應到標準名稱。"""
    lookup = _build_alias_lookup()
    rename: dict[str, str] = {}
    for col in df.columns:
        key = _normalize_header(col)
        if key in lookup:
            rename[col] = lookup[key]
    mapped = df.rename(columns=rename)
    warnings: list[str] = []
    for col in STANDARD_COLUMNS:
        if col not in mapped.columns:
            warnings.append(f"找不到欄位 {col},將以空值填入。")
            mapped[col] = pd.NA
    return mapped[STANDARD_COLUMNS], warnings


def normalize_status(value: object) -> str:
    if pd.isna(value):
        return "未知"
    text = str(value).strip().lower()
    if text in {s.lower() for s in COMPLETED_STATUS}:
        return "已完成"
    if text in {s.lower() for s in CANCELLED_STATUS}:
        return "已取消"
    if text in {s.lower() for s in REFUNDED_STATUS}:
        return "退貨"
    return str(value)


def calc_age(birth_year: object, ref_date: datetime | None = None) -> float:
    if pd.isna(birth_year):
        return float("nan")
    try:
        year = int(float(birth_year))
    except (TypeError, ValueError):
        return float("nan")
    ref = ref_date or datetime.now()
    age = ref.year - year
    if age < 0 or age > 120:
        return float("nan")
    return float(age)


def age_bucket(age: float) -> str:
    if pd.isna(age):
        return "未知"
    for low, high, label in zip(AGE_BINS[:-1], AGE_BINS[1:], AGE_LABELS):
        if low <= age < high:
            return label
    return "未知"


def _coerce_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def clean(df: pd.DataFrame, tz: str = DEFAULT_TZ) -> pd.DataFrame:
    """資料清理:型別轉換、時區、年齡桶。"""
    df = df.copy()

    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    if df["order_date"].dt.tz is None:
        df["order_date"] = df["order_date"].dt.tz_localize(tz, nonexistent="NaT", ambiguous="NaT")
    else:
        df["order_date"] = df["order_date"].dt.tz_convert(tz)

    df["order_amount"] = _coerce_numeric(df["order_amount"])
    df["unit_price"] = _coerce_numeric(df["unit_price"])
    df["quantity"] = _coerce_numeric(df["quantity"])
    df["subtotal"] = _coerce_numeric(df["subtotal"])
    df["birth_year"] = _coerce_numeric(df["birth_year"])

    # 若沒有 subtotal,用 unit_price * quantity 補
    missing_subtotal = df["subtotal"].isna()
    df.loc[missing_subtotal, "subtotal"] = df.loc[missing_subtotal, "unit_price"] * df.loc[missing_subtotal, "quantity"]

    df["order_status"] = df["order_status"].map(normalize_status)

    # 會員 ID:若空,以 email + phone 組合補
    fallback_id = (df["email"].fillna("").astype(str) + "|" + df["phone"].fillna("").astype(str))
    df["member_id"] = df["member_id"].where(df["member_id"].notna() & (df["member_id"].astype(str).str.strip() != ""), fallback_id)
    df["member_id"] = df["member_id"].astype(str).str.strip()

    # 文字欄位空值填「未知」
    for col in ["region", "gender", "product_category", "product_name", "sku"]:
        df[col] = df[col].fillna("未知").astype(str).str.strip().replace("", "未知")

    # 計算當下年齡
    now_local = datetime.now(pytz.timezone(tz))
    df["age"] = df["birth_year"].apply(lambda y: calc_age(y, now_local))
    df["age_bucket"] = df["age"].apply(age_bucket)

    naive = df["order_date"].dt.tz_localize(None)
    df["order_year"] = naive.dt.year
    df["order_month"] = naive.dt.to_period("M").astype(str)
    df["order_week"] = naive.dt.to_period("W").astype(str)
    df["order_day"] = naive.dt.date
    df["order_hour"] = naive.dt.hour
    df["order_dow"] = naive.dt.dayofweek  # 0 = Monday
    df["order_dow_name"] = naive.dt.day_name()

    return df


def aggregate_orders(df: pd.DataFrame) -> pd.DataFrame:
    """從訂單明細彙總到訂單層級(每列一張訂單)。"""
    if df.empty:
        return df.copy()
    agg = (
        df.groupby("order_id", as_index=False)
        .agg(
            order_date=("order_date", "min"),
            order_status=("order_status", "first"),
            member_id=("member_id", "first"),
            member_name=("member_name", "first"),
            birth_year=("birth_year", "first"),
            gender=("gender", "first"),
            region=("region", "first"),
            email=("email", "first"),
            phone=("phone", "first"),
            age=("age", "first"),
            age_bucket=("age_bucket", "first"),
            order_amount=("order_amount", "first"),
            line_total=("subtotal", "sum"),
            n_items=("quantity", "sum"),
            n_lines=("sku", "count"),
        )
    )
    # 若 order_amount 缺失,使用 line_total
    agg["order_amount"] = agg["order_amount"].fillna(agg["line_total"])
    od = pd.to_datetime(agg["order_date"])
    naive = od.dt.tz_localize(None) if od.dt.tz is not None else od
    agg["order_day"] = naive.dt.date
    agg["order_month"] = naive.dt.to_period("M").astype(str)
    agg["order_hour"] = naive.dt.hour
    agg["order_dow"] = naive.dt.dayofweek
    agg["order_dow_name"] = naive.dt.day_name()
    return agg


def load_excel(file, tz: str = DEFAULT_TZ) -> LoadResult:
    """讀取 Excel(支援檔案物件或路徑),回傳清理後資料。"""
    raw = pd.read_excel(file, engine="openpyxl")
    mapped, warnings = map_columns(raw)
    cleaned = clean(mapped, tz=tz)
    orders = aggregate_orders(cleaned)
    return LoadResult(df=cleaned, orders=orders, warnings=warnings)


def filter_status(df: pd.DataFrame, statuses: Iterable[str]) -> pd.DataFrame:
    statuses = list(statuses)
    if not statuses:
        return df.iloc[0:0]
    return df[df["order_status"].isin(statuses)].copy()
