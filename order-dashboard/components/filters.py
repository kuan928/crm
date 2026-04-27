"""側邊欄篩選器:時間區間、產品分類、會員分群、訂單狀態。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from metrics.member import segment_member


@dataclass
class FilterState:
    date_range: tuple[date, date]
    statuses: list[str]
    categories: list[str]
    member_segments: list[str]
    show_pii: bool
    sleeping_days: int
    churn_days: int
    exclude_recent_days: int


def _date_bounds(df: pd.DataFrame) -> tuple[date, date]:
    if df.empty or df["order_date"].isna().all():
        today = date.today()
        return today - timedelta(days=30), today
    od = df["order_date"]
    naive = od.dt.tz_localize(None) if od.dt.tz is not None else od
    return naive.min().date(), naive.max().date()


def render_sidebar(df: pd.DataFrame, orders: pd.DataFrame) -> FilterState:
    """渲染側邊欄篩選器,回傳目前選取的條件。"""
    st.sidebar.header("篩選條件")

    min_d, max_d = _date_bounds(df)
    date_range = st.sidebar.date_input(
        "訂單日期區間",
        value=(min_d, max_d),
        min_value=min_d,
        max_value=max_d,
        help="預設為資料的最早/最晚日期",
    )
    if isinstance(date_range, date):
        date_range = (date_range, date_range)
    elif len(date_range) == 1:
        date_range = (date_range[0], date_range[0])

    available_status = sorted(df["order_status"].dropna().unique().tolist())
    default_status = ["已完成"] if "已完成" in available_status else available_status
    statuses = st.sidebar.multiselect(
        "訂單狀態", available_status, default=default_status, help="預設只看已完成訂單"
    )

    categories = st.sidebar.multiselect(
        "產品分類",
        sorted(df["product_category"].dropna().unique().tolist()),
        default=[],
        help="不選=全部",
    )

    member_segments = st.sidebar.multiselect(
        "會員分群",
        ["新客", "回購客", "VIP", "沉睡客戶", "流失客戶"],
        default=[],
        help="不選=全部。分群會在套用時間/狀態篩選後計算。",
    )

    with st.sidebar.expander("進階參數", expanded=False):
        sleeping_days = st.number_input("沉睡天數門檻", value=90, min_value=1, step=5)
        churn_days = st.number_input("流失天數門檻", value=180, min_value=1, step=5)
        exclude_recent_days = st.number_input(
            "計算回購率時排除最近 N 天才首購的會員", value=30, min_value=0, step=5
        )

    show_pii = st.sidebar.toggle("顯示完整個資(姓名/Email/電話)", value=False)

    return FilterState(
        date_range=tuple(date_range),  # type: ignore[arg-type]
        statuses=statuses,
        categories=categories,
        member_segments=member_segments,
        show_pii=show_pii,
        sleeping_days=int(sleeping_days),
        churn_days=int(churn_days),
        exclude_recent_days=int(exclude_recent_days),
    )


def apply_filters(
    df: pd.DataFrame, orders: pd.DataFrame, state: FilterState
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """套用篩選器,回傳 (明細, 訂單彙總)。"""
    if df.empty:
        return df, orders

    od = df["order_date"]
    naive = od.dt.tz_localize(None) if od.dt.tz is not None else od
    start = pd.Timestamp(state.date_range[0])
    end = pd.Timestamp(state.date_range[1]) + pd.Timedelta(days=1)
    mask = (naive >= start) & (naive < end)
    df = df.loc[mask].copy()

    if state.statuses:
        df = df[df["order_status"].isin(state.statuses)]

    if state.categories:
        df = df[df["product_category"].isin(state.categories)]

    od2 = orders["order_date"]
    naive2 = od2.dt.tz_localize(None) if od2.dt.tz is not None else od2
    omask = (naive2 >= start) & (naive2 < end)
    orders = orders.loc[omask].copy()
    if state.statuses:
        orders = orders[orders["order_status"].isin(state.statuses)]
    if state.categories:
        order_ids_in_cat = df["order_id"].unique()
        orders = orders[orders["order_id"].isin(order_ids_in_cat)]

    if state.member_segments and not orders.empty:
        seg = segment_member(
            orders,
            sleeping_days=state.sleeping_days,
            churn_days=state.churn_days,
        )
        keep_ids = seg.loc[seg["segment"].isin(state.member_segments), "member_id"].tolist()
        orders = orders[orders["member_id"].isin(keep_ids)]
        df = df[df["member_id"].isin(keep_ids)]

    return df, orders


def mask_name(value: str) -> str:
    if not value or value == "未知":
        return value
    s = str(value)
    if len(s) <= 1:
        return s
    if len(s) == 2:
        return s[0] + "*"
    return s[0] + "*" * (len(s) - 2) + s[-1]


def mask_email(value: str) -> str:
    if not value or "@" not in str(value):
        return str(value)
    local, _, domain = str(value).partition("@")
    if len(local) <= 1:
        return f"{local}***@{domain}"
    return f"{local[0]}***@{domain}"


def mask_phone(value: str) -> str:
    s = str(value or "")
    if len(s) <= 4:
        return s
    return s[:3] + "*" * (len(s) - 5) + s[-2:]


def apply_pii_mask(df: pd.DataFrame, show_pii: bool) -> pd.DataFrame:
    """根據設定遮罩或還原 PII。"""
    if show_pii or df.empty:
        return df
    out = df.copy()
    if "member_name" in out.columns:
        out["member_name"] = out["member_name"].astype(str).map(mask_name)
    if "email" in out.columns:
        out["email"] = out["email"].astype(str).map(mask_email)
    if "phone" in out.columns:
        out["phone"] = out["phone"].astype(str).map(mask_phone)
    return out
