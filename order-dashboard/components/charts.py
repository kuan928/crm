"""共用圖表元件:Plotly 包裝 + 下載 CSV 按鈕。"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


def download_button(df: pd.DataFrame, label: str, filename: str, key: str | None = None) -> None:
    """提供 CSV 下載按鈕。"""
    if df is None or df.empty:
        return
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label=f"下載 CSV — {label}",
        data=csv,
        file_name=filename,
        mime="text/csv",
        key=key,
    )


def line_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    color: str | None = None,
    csv_name: str | None = None,
    key: str | None = None,
) -> None:
    if df is None or df.empty:
        st.info("此區間沒有資料。")
        return
    fig = px.line(df, x=x, y=y, color=color, markers=True, title=title)
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), height=380)
    st.plotly_chart(fig, use_container_width=True)
    if csv_name:
        download_button(df, title, csv_name, key=key)


def bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    color: str | None = None,
    orientation: str = "v",
    csv_name: str | None = None,
    key: str | None = None,
    text_auto: bool = True,
) -> None:
    if df is None or df.empty:
        st.info("此區間沒有資料。")
        return
    fig = px.bar(
        df, x=x, y=y, color=color, orientation=orientation, title=title, text_auto=text_auto
    )
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), height=420)
    st.plotly_chart(fig, use_container_width=True)
    if csv_name:
        download_button(df, title, csv_name, key=key)


def heatmap(
    matrix: pd.DataFrame,
    title: str,
    csv_name: str | None = None,
    key: str | None = None,
    colorscale: str = "Viridis",
) -> None:
    if matrix is None or matrix.empty:
        st.info("此區間沒有資料。")
        return
    fig = go.Figure(
        data=go.Heatmap(
            z=matrix.values,
            x=[str(c) for c in matrix.columns],
            y=[str(i) for i in matrix.index],
            colorscale=colorscale,
            hoverongaps=False,
        )
    )
    fig.update_layout(title=title, margin=dict(l=10, r=10, t=50, b=10), height=420)
    st.plotly_chart(fig, use_container_width=True)
    if csv_name:
        download_button(matrix.reset_index(), title, csv_name, key=key)


def histogram(
    series: pd.Series,
    title: str,
    nbins: int = 20,
    csv_name: str | None = None,
    key: str | None = None,
) -> None:
    if series is None or series.empty:
        st.info("此區間沒有資料。")
        return
    fig = px.histogram(series.to_frame(name="value"), x="value", nbins=nbins, title=title)
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), height=380)
    st.plotly_chart(fig, use_container_width=True)
    if csv_name:
        download_button(series.to_frame(name="value"), title, csv_name, key=key)


def kpi_card(label: str, value: str, delta: str | None = None) -> None:
    st.metric(label, value, delta=delta)


def fmt_currency(value: float) -> str:
    if pd.isna(value):
        return "—"
    return f"NT$ {value:,.0f}"


def fmt_int(value: float) -> str:
    if pd.isna(value):
        return "—"
    return f"{int(value):,}"


def fmt_pct(value: float) -> str:
    if pd.isna(value):
        return "—"
    return f"{value * 100:.1f}%"
