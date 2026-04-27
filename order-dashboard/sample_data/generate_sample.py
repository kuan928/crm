"""產生範例訂單資料(約 100 筆訂單,展開為多個明細列)。

執行:
    python sample_data/generate_sample.py
產出:sample_data/orders_sample.xlsx
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

random.seed(42)

REGIONS = ["台北市", "新北市", "桃園市", "台中市", "高雄市", "台南市", "新竹市", "宜蘭縣"]
GENDERS = ["男", "女", "其他"]
CATEGORIES = {
    "保養": ["精華液", "面霜", "化妝水", "面膜"],
    "彩妝": ["唇膏", "粉底液", "眼影盤", "腮紅"],
    "香氛": ["香水", "身體乳", "擴香"],
    "保健": ["維他命C", "葉黃素", "膠原蛋白"],
    "配件": ["化妝刷具", "美容工具", "化妝包"],
}
STATUSES = ["已完成"] * 18 + ["已取消"] * 1 + ["退貨"] * 1


def build_products() -> list[dict]:
    products = []
    sku_id = 1000
    for cat, items in CATEGORIES.items():
        for name in items:
            sku_id += 1
            products.append(
                {
                    "sku": f"SKU{sku_id}",
                    "product_name": name,
                    "product_category": cat,
                    "unit_price": random.choice([280, 380, 480, 680, 880, 1180, 1580, 2280]),
                }
            )
    return products


def build_members(n: int) -> list[dict]:
    members = []
    for i in range(1, n + 1):
        members.append(
            {
                "member_id": f"M{i:04d}",
                "member_name": f"會員{i:04d}",
                "birth_year": random.randint(1955, 2008),
                "gender": random.choices(GENDERS, weights=[35, 60, 5])[0],
                "region": random.choice(REGIONS),
                "email": f"user{i:04d}@example.com",
                "phone": f"09{random.randint(10000000, 99999999)}",
            }
        )
    return members


def main(out_path: Path, n_orders: int = 100, n_members: int = 40) -> None:
    products = build_products()
    members = build_members(n_members)

    # 讓部分會員多次回購,增加資料豐富度
    member_weights = [random.choice([1, 1, 1, 2, 3, 5]) for _ in members]

    rows: list[dict] = []
    end = datetime.now()
    start = end - timedelta(days=365)
    for order_idx in range(1, n_orders + 1):
        member = random.choices(members, weights=member_weights, k=1)[0]
        order_dt = start + timedelta(
            seconds=random.randint(0, int((end - start).total_seconds()))
        )
        status = random.choice(STATUSES)
        order_id = f"ORD{order_dt.strftime('%Y%m%d')}{order_idx:04d}"
        n_lines = random.choices([1, 2, 3, 4], weights=[55, 25, 15, 5])[0]
        chosen = random.sample(products, n_lines)
        order_total = 0.0
        line_rows = []
        for prod in chosen:
            qty = random.choices([1, 2, 3], weights=[75, 20, 5])[0]
            subtotal = prod["unit_price"] * qty
            order_total += subtotal
            line_rows.append(
                {
                    "訂單編號": order_id,
                    "訂單日期": order_dt,
                    "訂單狀態": status,
                    "會員ID": member["member_id"],
                    "會員姓名": member["member_name"],
                    "出生年": member["birth_year"],
                    "性別": member["gender"],
                    "地區": member["region"],
                    "Email": member["email"],
                    "電話": member["phone"],
                    "產品SKU": prod["sku"],
                    "產品名稱": prod["product_name"],
                    "產品分類": prod["product_category"],
                    "單價": prod["unit_price"],
                    "數量": qty,
                    "小計": subtotal,
                }
            )
        for r in line_rows:
            r["訂單金額"] = order_total
            rows.append(r)

    df = pd.DataFrame(rows)
    columns_order = [
        "訂單編號",
        "訂單日期",
        "訂單狀態",
        "訂單金額",
        "會員ID",
        "會員姓名",
        "出生年",
        "性別",
        "地區",
        "Email",
        "電話",
        "產品SKU",
        "產品名稱",
        "產品分類",
        "單價",
        "數量",
        "小計",
    ]
    df = df[columns_order]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(out_path, index=False, engine="openpyxl")
    print(f"已產生 {len(df)} 筆明細(共 {n_orders} 張訂單) → {out_path}")


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "orders_sample.xlsx"
    main(out)
