"""時間維度分析:小時、星期、月份、熱力圖。"""
from __future__ import annotations

import pandas as pd

DOW_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DOW_ZH = {
    "Monday": "週一",
    "Tuesday": "週二",
    "Wednesday": "週三",
    "Thursday": "週四",
    "Friday": "週五",
    "Saturday": "週六",
    "Sunday": "週日",
}


def revenue_trend(orders: pd.DataFrame, period: str = "M") -> pd.DataFrame:
    """營收趨勢:可切換日(D)、週(W)、月(M)。"""
    if orders.empty:
        return pd.DataFrame(columns=["period", "amount", "orders"])
    df = orders.copy()
    od = df["order_date"]
    naive = od.dt.tz_localize(None) if od.dt.tz is not None else od
    if period == "D":
        df["period"] = naive.dt.date.astype(str)
    elif period == "W":
        df["period"] = naive.dt.to_period("W").astype(str)
    else:
        df["period"] = naive.dt.to_period("M").astype(str)
    out = (
        df.groupby("period", as_index=False)
        .agg(amount=("order_amount", "sum"), orders=("order_id", "nunique"))
        .sort_values("period")
    )
    return out


def hourly_distribution(orders: pd.DataFrame) -> pd.DataFrame:
    if orders.empty:
        return pd.DataFrame({"hour": list(range(24)), "orders": [0] * 24})
    out = orders.groupby("order_hour").size().reindex(range(24), fill_value=0)
    return out.rename_axis("hour").reset_index(name="orders")


def dow_distribution(orders: pd.DataFrame) -> pd.DataFrame:
    if orders.empty:
        return pd.DataFrame({"dow": [DOW_ZH[d] for d in DOW_ORDER], "orders": [0] * 7})
    counts = orders["order_dow_name"].value_counts()
    counts = counts.reindex(DOW_ORDER, fill_value=0)
    return pd.DataFrame({"dow": [DOW_ZH[d] for d in counts.index], "orders": counts.values})


def hour_dow_heatmap(orders: pd.DataFrame) -> pd.DataFrame:
    if orders.empty:
        return pd.DataFrame()
    pivot = (
        orders.groupby(["order_dow_name", "order_hour"])
        .size()
        .unstack("order_hour", fill_value=0)
        .reindex(DOW_ORDER, fill_value=0)
    )
    pivot = pivot.reindex(columns=range(24), fill_value=0)
    pivot.index = [DOW_ZH[d] for d in pivot.index]
    return pivot


def monthly_seasonality(orders: pd.DataFrame) -> pd.DataFrame:
    if orders.empty:
        return pd.DataFrame({"month": list(range(1, 13)), "amount": [0] * 12})
    od = orders["order_date"]
    naive = od.dt.tz_localize(None) if od.dt.tz is not None else od
    df = orders.assign(month=naive.dt.month)
    out = df.groupby("month")["order_amount"].sum().reindex(range(1, 13), fill_value=0)
    return out.rename_axis("month").reset_index(name="amount")
