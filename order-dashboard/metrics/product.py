"""產品相關指標:銷量/金額排行、復購率、連帶購買。"""
from __future__ import annotations

from itertools import combinations

import pandas as pd


def product_ranking(
    df: pd.DataFrame, by: str = "amount", key: str = "sku", top_n: int | None = 20
) -> pd.DataFrame:
    """產品排行。

    Args:
        df: 訂單明細
        by: 'amount' 按金額排行,'quantity' 按銷量排行
        key: 'sku' 或 'product_name'
    """
    if df.empty:
        return pd.DataFrame(columns=[key, "product_name", "quantity", "amount", "buyers"])

    name_col = "product_name" if key != "product_name" else key
    grouped = df.groupby(key).agg(
        product_name=(name_col, "first"),
        quantity=("quantity", "sum"),
        amount=("subtotal", "sum"),
        buyers=("member_id", "nunique"),
    ).reset_index()

    sort_col = "amount" if by == "amount" else "quantity"
    grouped = grouped.sort_values(sort_col, ascending=False).reset_index(drop=True)
    if top_n:
        grouped = grouped.head(top_n)
    return grouped


def product_repurchase(df: pd.DataFrame, key: str = "sku") -> pd.DataFrame:
    """每個產品的復購率:同會員購買 ≥ 2 張不同訂單的比例。"""
    if df.empty:
        return pd.DataFrame(columns=[key, "product_name", "buyers", "repurchasers", "repurchase_rate"])

    name_col = "product_name"
    # 每個 (key, member) 的不同訂單數
    grp = df.groupby([key, "member_id"])["order_id"].nunique().reset_index(name="orders")
    name_map = df.drop_duplicates(key).set_index(key)[name_col]

    out = grp.groupby(key).agg(
        buyers=("member_id", "count"),
        repurchasers=("orders", lambda s: (s >= 2).sum()),
    ).reset_index()
    out["product_name"] = out[key].map(name_map)
    out["repurchase_rate"] = out["repurchasers"] / out["buyers"].replace(0, pd.NA)
    return out.sort_values("repurchase_rate", ascending=False, na_position="last")


def cooccurrence(df: pd.DataFrame, key: str = "sku", top_n: int = 10) -> pd.DataFrame:
    """連帶購買:同一張訂單內出現的產品配對 Top N。"""
    if df.empty:
        return pd.DataFrame(columns=["item_a", "item_b", "count", "name_a", "name_b"])

    name_map = df.drop_duplicates(key).set_index(key)["product_name"].to_dict()
    pairs: dict[tuple[str, str], int] = {}
    for _, group in df.groupby("order_id"):
        items = sorted(set(group[key].dropna().astype(str)))
        if len(items) < 2:
            continue
        for a, b in combinations(items, 2):
            pairs[(a, b)] = pairs.get((a, b), 0) + 1

    if not pairs:
        return pd.DataFrame(columns=["item_a", "item_b", "count", "name_a", "name_b"])

    out = (
        pd.DataFrame(
            [{"item_a": a, "item_b": b, "count": c} for (a, b), c in pairs.items()]
        )
        .sort_values("count", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
    out["name_a"] = out["item_a"].map(name_map)
    out["name_b"] = out["item_b"].map(name_map)
    return out


def category_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """分類維度的營收佔比。"""
    if df.empty:
        return pd.DataFrame(columns=["product_category", "amount", "share"])
    out = df.groupby("product_category", as_index=False)["subtotal"].sum().rename(columns={"subtotal": "amount"})
    total = out["amount"].sum() or 1
    out["share"] = out["amount"] / total
    return out.sort_values("amount", ascending=False)
