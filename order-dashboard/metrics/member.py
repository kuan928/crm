"""會員相關指標:回購率、RFM、同期群分析。"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytz


def _ensure_naive(series: pd.Series) -> pd.Series:
    if series.dt.tz is not None:
        return series.dt.tz_localize(None)
    return series


def member_first_purchase(orders: pd.DataFrame) -> pd.DataFrame:
    """每個會員的首購日期。"""
    if orders.empty:
        return pd.DataFrame(columns=["member_id", "first_order_date", "last_order_date"])
    first = (
        orders.groupby("member_id", as_index=False)
        .agg(first_order_date=("order_date", "min"), last_order_date=("order_date", "max"))
    )
    return first


def repurchase_rate(
    orders: pd.DataFrame,
    exclude_recent_days: int = 30,
    ref_date: datetime | None = None,
) -> dict:
    """整體回購率。

    回購率 = 購買 ≥ 2 張不同訂單的會員 / 總會員(排除最近 exclude_recent_days
    才首購的會員)。
    """
    if orders.empty:
        return {"rate": 0.0, "repurchasers": 0, "total": 0, "excluded_new": 0}

    ref = ref_date or datetime.now()
    if isinstance(ref, datetime) and ref.tzinfo is None:
        ref = pytz.timezone("Asia/Taipei").localize(ref)

    counts = orders.groupby("member_id")["order_id"].nunique()
    first = orders.groupby("member_id")["order_date"].min()

    cutoff = ref - timedelta(days=exclude_recent_days)
    eligible = first[first <= cutoff].index
    excluded = len(first) - len(eligible)
    if len(eligible) == 0:
        return {"rate": 0.0, "repurchasers": 0, "total": 0, "excluded_new": excluded}

    eligible_counts = counts.loc[eligible]
    repurchasers = int((eligible_counts >= 2).sum())
    total = int(len(eligible))
    return {
        "rate": repurchasers / total if total else 0.0,
        "repurchasers": repurchasers,
        "total": total,
        "excluded_new": excluded,
    }


def repurchase_distribution(orders: pd.DataFrame) -> pd.DataFrame:
    """回購次數分佈(以訂單數計):1 / 2 / 3 / 4+。"""
    if orders.empty:
        return pd.DataFrame(columns=["bucket", "members"])
    counts = orders.groupby("member_id")["order_id"].nunique()

    def bucket(n: int) -> str:
        if n >= 4:
            return "4+ 次"
        return f"{n} 次"

    dist = counts.map(bucket).value_counts().reindex(["1 次", "2 次", "3 次", "4+ 次"], fill_value=0)
    return dist.rename_axis("bucket").reset_index(name="members")


def first_to_second_interval(orders: pd.DataFrame) -> pd.Series:
    """首購到第二次購買的間隔天數。"""
    if orders.empty:
        return pd.Series(dtype="float64")
    sorted_orders = orders.sort_values(["member_id", "order_date"])
    first_two = sorted_orders.groupby("member_id").head(2)
    counts = first_two.groupby("member_id").size()
    eligible = counts[counts >= 2].index
    pairs = first_two[first_two["member_id"].isin(eligible)]
    pivot = pairs.groupby("member_id")["order_date"].agg(["min", "max"])
    intervals = (pivot["max"] - pivot["min"]).dt.days
    return intervals[intervals > 0]


def rfm_table(orders: pd.DataFrame, ref_date: datetime | None = None) -> pd.DataFrame:
    """計算每個會員的 R/F/M 原始值與 1-5 分數,以及分群標籤。"""
    if orders.empty:
        cols = ["member_id", "recency_days", "frequency", "monetary", "R", "F", "M", "segment"]
        return pd.DataFrame(columns=cols)

    ref = ref_date or orders["order_date"].max()
    ref = pd.to_datetime(ref)
    if ref.tzinfo is None and orders["order_date"].dt.tz is not None:
        ref = ref.tz_localize(orders["order_date"].dt.tz)

    g = orders.groupby("member_id")
    rfm = pd.DataFrame(
        {
            "recency_days": (ref - g["order_date"].max()).dt.days,
            "frequency": g["order_id"].nunique(),
            "monetary": g["order_amount"].sum(),
        }
    ).reset_index()

    # 分數:Recency 越小越好(分數高);F、M 越大越好
    rfm["R"] = _score(rfm["recency_days"], reverse=True)
    rfm["F"] = _score(rfm["frequency"], reverse=False)
    rfm["M"] = _score(rfm["monetary"], reverse=False)

    rfm["segment"] = rfm.apply(_rfm_segment, axis=1)
    return rfm


def _score(values: pd.Series, reverse: bool, q: int = 5) -> pd.Series:
    """以分位數產生 1-5 分。reverse=True 表示值越小分數越高(用於 Recency)。"""
    if values.nunique() <= 1:
        return pd.Series([3] * len(values), index=values.index)
    try:
        ranks = pd.qcut(values.rank(method="first"), q=q, labels=False) + 1
    except ValueError:
        ranks = pd.cut(values, bins=q, labels=False) + 1
    if reverse:
        ranks = q + 1 - ranks
    return ranks.astype(int)


def _rfm_segment(row: pd.Series) -> str:
    r, f, m = row["R"], row["F"], row["M"]
    if r >= 4 and f >= 4 and m >= 4:
        return "VIP"
    if f >= 4 and m >= 3:
        return "忠實客戶"
    if r >= 4 and f <= 2:
        return "潛力客戶"
    if r <= 2 and f >= 3:
        return "沉睡客戶"
    if r <= 2:
        return "流失客戶"
    return "一般客戶"


def segment_summary(rfm: pd.DataFrame) -> pd.DataFrame:
    if rfm.empty:
        return pd.DataFrame(columns=["segment", "members", "monetary", "share"])
    summary = (
        rfm.groupby("segment", as_index=False)
        .agg(members=("member_id", "count"), monetary=("monetary", "sum"))
        .sort_values("monetary", ascending=False)
    )
    total = summary["monetary"].sum() or 1
    summary["share"] = summary["monetary"] / total
    return summary


def cohort_retention(orders: pd.DataFrame, max_periods: int = 12) -> pd.DataFrame:
    """以「首購月份」為同期群,計算後續每月的留存率(獨立會員數佔首購群體比例)。"""
    if orders.empty:
        return pd.DataFrame()

    df = orders[["member_id", "order_date"]].copy()
    df["order_month"] = df["order_date"].dt.to_period("M") if df["order_date"].dt.tz is None else df["order_date"].dt.tz_localize(None).dt.to_period("M")
    first_month = df.groupby("member_id")["order_month"].min().rename("cohort")
    df = df.merge(first_month, on="member_id")
    df["period"] = (df["order_month"] - df["cohort"]).apply(lambda x: x.n if pd.notna(x) else np.nan)
    df = df[df["period"] <= max_periods]

    cohort_sizes = df.groupby("cohort")["member_id"].nunique()
    pivot = (
        df.groupby(["cohort", "period"])["member_id"]
        .nunique()
        .unstack("period")
        .fillna(0)
    )
    retention = pivot.divide(cohort_sizes, axis=0).round(3)
    retention.index = retention.index.astype(str)
    retention.columns = [f"M+{int(c)}" for c in retention.columns]
    return retention


def segment_member(
    orders: pd.DataFrame,
    sleeping_days: int = 90,
    churn_days: int = 180,
    ref_date: datetime | None = None,
) -> pd.DataFrame:
    """以「最近購買距今天數」與「訂單數」為依據,將會員分為新客/回購/VIP/沉睡/流失。"""
    if orders.empty:
        return pd.DataFrame(columns=["member_id", "segment"])

    ref = ref_date or orders["order_date"].max()
    ref = pd.to_datetime(ref)
    if ref.tzinfo is None and orders["order_date"].dt.tz is not None:
        ref = ref.tz_localize(orders["order_date"].dt.tz)

    g = orders.groupby("member_id")
    latest = g["order_date"].max()
    counts = g["order_id"].nunique()
    spending = g["order_amount"].sum()

    days_since = (ref - latest).dt.days

    def label(days: int, n: int, total: float) -> str:
        if days >= churn_days:
            return "流失客戶"
        if days >= sleeping_days:
            return "沉睡客戶"
        if n == 1:
            return "新客"
        if n >= 4 or total >= spending.quantile(0.8):
            return "VIP"
        return "回購客"

    segs = [label(d, n, t) for d, n, t in zip(days_since, counts, spending)]
    return pd.DataFrame(
        {
            "member_id": latest.index,
            "segment": segs,
            "last_order_days": days_since.values,
            "orders": counts.values,
            "monetary": spending.values,
        }
    )


def new_vs_returning_revenue(
    orders: pd.DataFrame, period: str = "M"
) -> pd.DataFrame:
    """每段時間的新客 vs 老客營收(以「該訂單之前是否有購買紀錄」判斷)。"""
    if orders.empty:
        return pd.DataFrame()

    df = orders.sort_values("order_date").copy()
    df["is_first"] = ~df.duplicated("member_id", keep="first")
    df["customer_type"] = np.where(df["is_first"], "新客", "老客")

    naive = _ensure_naive(df["order_date"])
    if period == "D":
        df["period"] = naive.dt.date.astype(str)
    elif period == "W":
        df["period"] = naive.dt.to_period("W").astype(str)
    else:
        df["period"] = naive.dt.to_period("M").astype(str)

    out = (
        df.groupby(["period", "customer_type"], as_index=False)["order_amount"].sum()
    )
    return out
