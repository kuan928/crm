"""會員輪廓:年齡、性別、地區分佈。"""
from __future__ import annotations

import pandas as pd

from data_loader import AGE_LABELS


def age_distribution(orders: pd.DataFrame) -> pd.DataFrame:
    """以「會員」為單位的年齡層分佈(每位會員只算一次)。"""
    if orders.empty:
        return pd.DataFrame({"age_bucket": AGE_LABELS + ["未知"], "members": [0] * (len(AGE_LABELS) + 1)})
    member_age = orders.drop_duplicates("member_id")[["member_id", "age_bucket"]]
    counts = member_age["age_bucket"].value_counts()
    order_labels = AGE_LABELS + ["未知"]
    counts = counts.reindex(order_labels, fill_value=0)
    return counts.rename_axis("age_bucket").reset_index(name="members")


def gender_distribution(orders: pd.DataFrame) -> pd.DataFrame:
    if orders.empty:
        return pd.DataFrame(columns=["gender", "members"])
    member_gender = orders.drop_duplicates("member_id")[["member_id", "gender"]]
    return (
        member_gender["gender"].value_counts().rename_axis("gender").reset_index(name="members")
    )


def region_distribution(orders: pd.DataFrame) -> pd.DataFrame:
    if orders.empty:
        return pd.DataFrame(columns=["region", "members", "amount"])
    member_region = orders.drop_duplicates("member_id")[["member_id", "region"]]
    counts = member_region["region"].value_counts().rename_axis("region").reset_index(name="members")
    spending = orders.groupby("region", as_index=False)["order_amount"].sum().rename(columns={"order_amount": "amount"})
    return counts.merge(spending, on="region", how="left").sort_values("members", ascending=False)


def aov_by_age(orders: pd.DataFrame) -> pd.DataFrame:
    """各年齡層的客單價(AOV)與中位數。"""
    if orders.empty:
        return pd.DataFrame(columns=["age_bucket", "aov", "median", "orders"])
    out = (
        orders.groupby("age_bucket")
        .agg(aov=("order_amount", "mean"), median=("order_amount", "median"), orders=("order_id", "nunique"))
        .reset_index()
    )
    order_labels = AGE_LABELS + ["未知"]
    out["age_bucket"] = pd.Categorical(out["age_bucket"], categories=order_labels, ordered=True)
    return out.sort_values("age_bucket")


def category_by_age(df: pd.DataFrame) -> pd.DataFrame:
    """各年齡層偏好的產品分類(以小計金額計)。"""
    if df.empty:
        return pd.DataFrame(columns=["age_bucket", "product_category", "amount"])
    out = (
        df.groupby(["age_bucket", "product_category"], as_index=False)["subtotal"].sum().rename(columns={"subtotal": "amount"})
    )
    order_labels = AGE_LABELS + ["未知"]
    out["age_bucket"] = pd.Categorical(out["age_bucket"], categories=order_labels, ordered=True)
    return out.sort_values(["age_bucket", "amount"], ascending=[True, False])
