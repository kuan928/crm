"""訂單分析互動式儀表板 — Streamlit 主程式。

執行:
    streamlit run app.py

頁面:總覽 / 會員分析 / 產品分析 / 時間分析 / 會員輪廓
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from components import charts as ch
from components.filters import FilterState, apply_filters, apply_pii_mask, render_sidebar
from data_loader import LoadResult, load_excel
from metrics import demographics as dm
from metrics import member as mm
from metrics import product as pm
from metrics import time_analysis as tm

st.set_page_config(page_title="訂單分析儀表板", page_icon="📊", layout="wide")


@st.cache_data(show_spinner="讀取與清理資料中…")
def cached_load(file_bytes: bytes, name: str) -> LoadResult:
    """以檔案內容做為快取 key,避免重新上傳同檔仍重新計算。"""
    import io

    return load_excel(io.BytesIO(file_bytes))


def load_default_sample() -> LoadResult | None:
    sample = Path(__file__).parent / "sample_data" / "orders_sample.xlsx"
    if sample.exists():
        return load_excel(sample)
    return None


def render_data_summary(result: LoadResult) -> None:
    df = result.df
    st.markdown("**資料概況**")
    cols = st.columns(4)
    cols[0].metric("總明細筆數", ch.fmt_int(len(df)))
    cols[1].metric("訂單張數", ch.fmt_int(df["order_id"].nunique()))
    if not df.empty and df["order_date"].notna().any():
        od = df["order_date"]
        naive = od.dt.tz_localize(None) if od.dt.tz is not None else od
        cols[2].metric("日期範圍", f"{naive.min().date()} ~ {naive.max().date()}")
    else:
        cols[2].metric("日期範圍", "—")
    cols[3].metric("會員數 / 產品數", f"{df['member_id'].nunique()} / {df['sku'].nunique()}")

    missing_critical = [
        std for std in ("order_id", "order_date", "member_id", "sku")
        if std not in result.column_mapping.values()
    ]
    if missing_critical:
        st.error(
            "⚠️ 偵測到關鍵欄位沒有對應上,儀表板會顯示空白或錯誤的數字。\n\n"
            f"沒有對應到的欄位:`{'`, `'.join(missing_critical)}`\n\n"
            "請展開下方「欄位對應檢查」,告訴我你 Excel 的欄位該對應到哪個標準欄位。"
        )

    with st.expander(
        "🔍 欄位對應檢查(若儀表板數字異常請打開)",
        expanded=bool(missing_critical),
    ):
        st.markdown("**Excel 中的所有欄位**(共 {} 欄):".format(len(result.original_columns)))
        st.code(" | ".join(result.original_columns) or "(無)", language=None)

        if result.column_mapping:
            st.markdown("**已對應上的欄位**:")
            mapping_df = pd.DataFrame(
                [{"Excel 欄名": k, "→ 標準欄位": v} for k, v in result.column_mapping.items()]
            )
            st.dataframe(mapping_df, use_container_width=True, hide_index=True)
        else:
            st.warning("沒有任何欄位被自動對應上!")

        if result.warnings:
            st.markdown("**沒有對應上的標準欄位**:")
            for w in result.warnings:
                st.markdown(f"- {w}")
            st.info(
                "💡 想加自訂對應?編輯 `data_loader.py` 的 `COLUMN_ALIASES`,或把 Excel 第一列的欄名改成上方標準欄名(例如把「訂購日期」改成「訂單日期」)。"
            )


def page_overview(df: pd.DataFrame, orders: pd.DataFrame, state: FilterState) -> None:
    st.subheader("總覽")
    if orders.empty:
        st.info("目前篩選結果沒有資料,請調整側邊欄條件。")
        return

    total_revenue = orders["order_amount"].sum()
    total_orders = orders["order_id"].nunique()
    total_members = orders["member_id"].nunique()
    aov_mean = orders["order_amount"].mean()
    aov_median = orders["order_amount"].median()
    rep = mm.repurchase_rate(orders, exclude_recent_days=state.exclude_recent_days)

    cols = st.columns(5)
    cols[0].metric("總營收", ch.fmt_currency(total_revenue))
    cols[1].metric("總訂單數", ch.fmt_int(total_orders))
    cols[2].metric("總會員數", ch.fmt_int(total_members))
    cols[3].metric(
        "平均客單價 (中位數)",
        ch.fmt_currency(aov_mean),
        delta=f"中位數 {ch.fmt_currency(aov_median)}",
        delta_color="off",
    )
    cols[4].metric(
        "回購率",
        ch.fmt_pct(rep["rate"]),
        delta=f"已排除最近 {state.exclude_recent_days} 天首購 {rep['excluded_new']} 人",
        delta_color="off",
    )

    st.divider()

    granularity = st.radio(
        "趨勢顆粒度",
        ["日", "週", "月"],
        index=2,
        horizontal=True,
        key="overview_granularity",
    )
    period = {"日": "D", "週": "W", "月": "M"}[granularity]
    trend = tm.revenue_trend(orders, period=period)
    ch.line_chart(
        trend,
        x="period",
        y="amount",
        title=f"營收趨勢({granularity})",
        csv_name="revenue_trend.csv",
        key="dl_overview_trend",
    )

    nvr = mm.new_vs_returning_revenue(orders, period=period)
    if not nvr.empty:
        nvr = nvr.rename(columns={"order_amount": "amount"})
        ch.bar_chart(
            nvr,
            x="period",
            y="amount",
            color="customer_type",
            title="新客 vs 老客 營收",
            csv_name="new_vs_returning.csv",
            key="dl_overview_nvr",
        )


def page_member(df: pd.DataFrame, orders: pd.DataFrame, state: FilterState) -> None:
    st.subheader("會員分析")
    if orders.empty:
        st.info("目前篩選結果沒有資料。")
        return

    rep = mm.repurchase_rate(orders, exclude_recent_days=state.exclude_recent_days)
    cols = st.columns(3)
    cols[0].metric("整體回購率", ch.fmt_pct(rep["rate"]))
    cols[1].metric("回購會員 / 樣本會員", f"{rep['repurchasers']} / {rep['total']}")
    cols[2].metric("被排除的新客", ch.fmt_int(rep["excluded_new"]))

    dist = mm.repurchase_distribution(orders)
    ch.bar_chart(
        dist,
        x="bucket",
        y="members",
        title="回購次數分佈",
        csv_name="repurchase_distribution.csv",
        key="dl_member_dist",
    )

    intervals = mm.first_to_second_interval(orders)
    if not intervals.empty:
        st.markdown(
            f"**首購 → 第二次購買間隔**:平均 {intervals.mean():.1f} 天 / 中位數 {intervals.median():.0f} 天"
        )
        ch.histogram(
            intervals,
            title="首購到第二次購買的間隔天數",
            nbins=15,
            csv_name="first_to_second_interval.csv",
            key="dl_member_interval",
        )

    st.divider()
    st.markdown("### RFM 分群")
    rfm = mm.rfm_table(orders)
    summary = mm.segment_summary(rfm)
    ch.bar_chart(
        summary,
        x="segment",
        y="members",
        title="各分群人數",
        csv_name="rfm_segments.csv",
        key="dl_rfm_seg",
    )
    if not summary.empty:
        st.dataframe(
            summary.assign(
                share=lambda d: (d["share"] * 100).round(1).astype(str) + "%",
                monetary=lambda d: d["monetary"].map(ch.fmt_currency),
            ),
            use_container_width=True,
        )

    st.markdown("### 會員 RFM 明細")
    rfm_show = rfm.copy()
    rfm_show["monetary"] = rfm_show["monetary"].map(ch.fmt_currency)
    rfm_show = apply_pii_mask(rfm_show, state.show_pii)
    st.dataframe(rfm_show, use_container_width=True, height=320)
    ch.download_button(rfm, "RFM 明細", "rfm_detail.csv", key="dl_rfm_detail")

    st.divider()
    st.markdown("### 同期群留存率(以首購月為群組)")
    cohort = mm.cohort_retention(orders)
    if cohort.empty:
        st.info("資料量不足以計算同期群。")
    else:
        display = (cohort * 100).round(1)
        ch.heatmap(
            display,
            title="留存率 %(列=首購月,行=後續第 N 個月)",
            csv_name="cohort_retention.csv",
            key="dl_cohort",
        )


def page_product(df: pd.DataFrame, orders: pd.DataFrame, state: FilterState) -> None:
    st.subheader("產品分析")
    if df.empty:
        st.info("目前篩選結果沒有資料。")
        return

    col1, col2 = st.columns(2)
    by = col1.radio("排行依據", ["金額", "銷量"], index=0, horizontal=True, key="prod_by")
    key = col2.radio("產品識別", ["SKU", "商品名稱"], index=0, horizontal=True, key="prod_key")
    by_arg = "amount" if by == "金額" else "quantity"
    key_arg = "sku" if key == "SKU" else "product_name"

    ranking = pm.product_ranking(df, by=by_arg, key=key_arg, top_n=20)
    if not ranking.empty:
        plot_df = ranking.copy()
        label_col = "product_name" if key_arg == "sku" else "product_name"
        plot_df["label"] = (
            plot_df[key_arg].astype(str) + " — " + plot_df[label_col].astype(str)
        ).str.slice(0, 30)
        plot_df = plot_df.sort_values(by_arg)
        ch.bar_chart(
            plot_df,
            x=by_arg,
            y="label",
            orientation="h",
            title=f"Top 20 產品({by})",
            csv_name="product_ranking.csv",
            key="dl_prod_rank",
        )
        full = pm.product_ranking(df, by=by_arg, key=key_arg, top_n=None)
        ch.download_button(full, "完整產品排行", "product_ranking_full.csv", key="dl_prod_full")

    st.divider()
    st.markdown("### 產品復購率")
    repurch = pm.product_repurchase(df, key=key_arg)
    if not repurch.empty:
        top_high = repurch.head(15).copy()
        top_high["repurchase_rate_pct"] = (top_high["repurchase_rate"] * 100).round(1)
        ch.bar_chart(
            top_high.sort_values("repurchase_rate_pct"),
            x="repurchase_rate_pct",
            y="product_name",
            orientation="h",
            title="復購率 Top 15(%)",
            csv_name="product_repurchase_top.csv",
            key="dl_prod_rep_top",
        )
        ch.download_button(repurch, "完整復購率表", "product_repurchase_full.csv", key="dl_prod_rep_full")

    st.divider()
    st.markdown("### 連帶購買 — 「買 A 的人也買了 B」Top 10")
    co = pm.cooccurrence(df, key=key_arg, top_n=10)
    if co.empty:
        st.info("沒有足夠的多品項訂單以計算連帶購買。")
    else:
        st.dataframe(co, use_container_width=True)
        ch.download_button(co, "連帶購買", "cooccurrence.csv", key="dl_prod_co")

    st.divider()
    st.markdown("### 各分類營收佔比")
    cat = pm.category_breakdown(df)
    if not cat.empty:
        cat_show = cat.copy()
        cat_show["share_pct"] = (cat_show["share"] * 100).round(1)
        ch.bar_chart(
            cat_show,
            x="product_category",
            y="amount",
            title="各分類營收",
            csv_name="category_breakdown.csv",
            key="dl_prod_cat",
        )


def page_time(df: pd.DataFrame, orders: pd.DataFrame, state: FilterState) -> None:
    st.subheader("時間分析")
    if orders.empty:
        st.info("目前篩選結果沒有資料。")
        return

    hourly = tm.hourly_distribution(orders)
    ch.bar_chart(
        hourly,
        x="hour",
        y="orders",
        title="24 小時下單熱度",
        csv_name="hourly.csv",
        key="dl_time_hour",
    )

    dow = tm.dow_distribution(orders)
    ch.bar_chart(
        dow,
        x="dow",
        y="orders",
        title="星期幾下單分佈",
        csv_name="dow.csv",
        key="dl_time_dow",
    )

    monthly = tm.monthly_seasonality(orders)
    ch.bar_chart(
        monthly,
        x="month",
        y="amount",
        title="月份/季節營收",
        csv_name="monthly.csv",
        key="dl_time_month",
    )

    matrix = tm.hour_dow_heatmap(orders)
    ch.heatmap(
        matrix,
        title="時段 × 星期 訂單熱力圖",
        csv_name="hour_dow_heatmap.csv",
        key="dl_time_heat",
    )


def page_demographics(df: pd.DataFrame, orders: pd.DataFrame, state: FilterState) -> None:
    st.subheader("會員輪廓")
    if df.empty:
        st.info("目前篩選結果沒有資料。")
        return

    age = dm.age_distribution(orders)
    ch.bar_chart(
        age,
        x="age_bucket",
        y="members",
        title="年齡分佈(以會員為單位)",
        csv_name="age_distribution.csv",
        key="dl_demo_age",
    )

    gender = dm.gender_distribution(orders)
    if not gender.empty:
        ch.bar_chart(
            gender,
            x="gender",
            y="members",
            title="性別分佈",
            csv_name="gender_distribution.csv",
            key="dl_demo_gender",
        )

    region = dm.region_distribution(orders)
    if not region.empty:
        ch.bar_chart(
            region.head(15),
            x="region",
            y="members",
            title="地區分佈(Top 15)",
            csv_name="region_distribution.csv",
            key="dl_demo_region",
        )

    aov = dm.aov_by_age(orders)
    if not aov.empty:
        aov_show = aov.copy()
        aov_show["age_bucket"] = aov_show["age_bucket"].astype(str)
        ch.bar_chart(
            aov_show,
            x="age_bucket",
            y="aov",
            title="各年齡層客單價(平均)",
            csv_name="aov_by_age.csv",
            key="dl_demo_aov",
        )
        st.dataframe(
            aov_show.assign(
                aov=lambda d: d["aov"].map(ch.fmt_currency),
                median=lambda d: d["median"].map(ch.fmt_currency),
            ),
            use_container_width=True,
        )

    cat_age = dm.category_by_age(df)
    if not cat_age.empty:
        ca = cat_age.copy()
        ca["age_bucket"] = ca["age_bucket"].astype(str)
        ch.bar_chart(
            ca,
            x="age_bucket",
            y="amount",
            color="product_category",
            title="各年齡層偏好的產品分類(營收)",
            csv_name="category_by_age.csv",
            key="dl_demo_cat_age",
        )


def main() -> None:
    st.title("📊 訂單分析儀表板")
    st.caption("上傳訂單 Excel,即時分析會員、產品、時間、年齡多維度指標。")

    uploaded = st.sidebar.file_uploader(
        "上傳訂單 Excel(支援拖拉)", type=["xlsx", "xls"], accept_multiple_files=False
    )
    use_sample = st.sidebar.checkbox("使用範例資料", value=uploaded is None)

    result: LoadResult | None = None
    if uploaded is not None:
        result = cached_load(uploaded.getvalue(), uploaded.name)
    elif use_sample:
        with st.spinner("讀取範例資料中…"):
            result = load_default_sample()
        if result is None:
            st.warning("找不到 sample_data/orders_sample.xlsx。請執行 `python sample_data/generate_sample.py` 產生。")

    if result is None:
        st.info("請從側邊欄上傳 Excel,或勾選「使用範例資料」。")
        return

    render_data_summary(result)
    state = render_sidebar(result.df, result.orders)

    df, orders = apply_filters(result.df, result.orders, state)

    tabs = st.tabs(["總覽", "會員分析", "產品分析", "時間分析", "會員輪廓"])
    with tabs[0]:
        page_overview(df, orders, state)
    with tabs[1]:
        page_member(df, orders, state)
    with tabs[2]:
        page_product(df, orders, state)
    with tabs[3]:
        page_time(df, orders, state)
    with tabs[4]:
        page_demographics(df, orders, state)


if __name__ == "__main__":
    main()
