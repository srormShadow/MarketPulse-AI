import pandas as pd
import matplotlib.pyplot as plt

# Load dataset
sales = pd.read_csv("data/demo_sales_365.csv")
sales["date"] = pd.to_datetime(sales["date"])

# Aggregate by category
# If category not in sales file, join with SKU master
sku = pd.read_csv("data/demo_sku_master.csv")

df = sales.merge(sku[["sku_id", "category"]], on="sku_id")

category_daily = (
    df.groupby(["date", "category"])["units_sold"]
    .sum()
    .reset_index()
)

# Plot each category
for category in category_daily["category"].unique():
    subset = category_daily[category_daily["category"] == category]
    
    plt.figure(figsize=(12, 5))
    plt.plot(subset["date"], subset["units_sold"])
    plt.title(f"{category} - Daily Demand (2024)")
    plt.xlabel("Date")
    plt.ylabel("Units Sold")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()