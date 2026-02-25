"""Generate a realistic synthetic retail dataset for one store.

Outputs:
- data/demo_sku_master.csv
- data/demo_sales_365.csv
- data/demo_festival_spikes_snacks.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def build_sku_master() -> pd.DataFrame:
    """Create SKU master data (7 SKUs across 3 categories)."""

    skus = [
        {"sku_id": "OIL_1L_SUN", "product_name": "Sunflower Oil 1L", "category": "Edible Oil", "mrp": 180.0, "cost": 145.0, "current_inventory": 420},
        {"sku_id": "OIL_1L_GND", "product_name": "Groundnut Oil 1L", "category": "Edible Oil", "mrp": 210.0, "cost": 168.0, "current_inventory": 390},
        {"sku_id": "STP_RICE_5KG", "product_name": "Rice 5kg", "category": "Staples", "mrp": 340.0, "cost": 280.0, "current_inventory": 250},
        {"sku_id": "STP_DAL_1KG", "product_name": "Toor Dal 1kg", "category": "Staples", "mrp": 160.0, "cost": 130.0, "current_inventory": 300},
        {"sku_id": "SNK_CHIPS_50G", "product_name": "Potato Chips 50g", "category": "Snacks", "mrp": 20.0, "cost": 11.0, "current_inventory": 900},
        {"sku_id": "SNK_BISCUIT_100G", "product_name": "Butter Biscuit 100g", "category": "Snacks", "mrp": 35.0, "cost": 22.0, "current_inventory": 780},
        {"sku_id": "SNK_NAMKEEN_200G", "product_name": "Namkeen 200g", "category": "Snacks", "mrp": 55.0, "cost": 33.0, "current_inventory": 640},
    ]
    return pd.DataFrame(skus)


def category_demand_bounds() -> dict[str, tuple[int, int]]:
    """Base demand ranges requested for each category."""

    return {
        "Edible Oil": (80, 120),
        "Staples": (40, 70),
        "Snacks": (100, 150),
    }


def festival_calendar_2024() -> dict[str, dict[str, object]]:
    """Festival configuration with fixed 2024 dates and impact intensity."""

    return {
        "Pongal": {"date": pd.Timestamp("2024-01-15"), "intensity": "MODERATE"},
        "Holi": {"date": pd.Timestamp("2024-03-25"), "intensity": "MODERATE"},
        "Eid": {"date": pd.Timestamp("2024-04-10"), "intensity": "HIGH"},
        "Independence Day": {"date": pd.Timestamp("2024-08-15"), "intensity": "MINOR"},
        "Navratri": {"date": pd.Timestamp("2024-10-03"), "intensity": "MODERATE"},
        "Diwali": {"date": pd.Timestamp("2024-11-01"), "intensity": "VERY_HIGH"},
        "Christmas": {"date": pd.Timestamp("2024-12-25"), "intensity": "HIGH"},
        "New Year": {"date": pd.Timestamp("2024-12-31"), "intensity": "MINOR"},
    }


def intensity_base_uplift() -> dict[str, float]:
    """Base uplift by festival intensity level."""

    return {
        "VERY_HIGH": 0.45,
        "HIGH": 0.28,
        "MODERATE": 0.18,
        "MINOR": 0.10,
    }


def category_festival_weights() -> dict[str, dict[str, float]]:
    """Category-specific multiplier for each festival effect."""

    return {
        "Edible Oil": {
            "Pongal": 1.00,
            "Holi": 0.60,
            "Eid": 1.30,
            "Independence Day": 0.50,
            "Navratri": 0.70,
            "Diwali": 1.35,
            "Christmas": 0.60,
            "New Year": 0.50,
        },
        "Staples": {
            "Pongal": 0.95,
            "Holi": 0.65,
            "Eid": 1.25,
            "Independence Day": 0.55,
            "Navratri": 0.75,
            "Diwali": 1.20,
            "Christmas": 0.70,
            "New Year": 0.55,
        },
        "Snacks": {
            "Pongal": 0.70,
            "Holi": 0.85,
            "Eid": 0.80,
            "Independence Day": 0.45,
            "Navratri": 0.90,
            "Diwali": 1.20,
            "Christmas": 1.10,
            "New Year": 0.55,
        },
    }


def weekend_factor(category: str, day_of_week: int) -> float:
    """Return weekly seasonal adjustment by category."""

    is_weekend = day_of_week >= 5
    if category == "Snacks":
        return 1.15 if is_weekend else 1.0
    if category == "Edible Oil":
        return 1.05 if is_weekend else 1.0
    return 1.01 if is_weekend else 0.99


def noise_scale(category: str) -> float:
    """Return Gaussian noise scale by category."""

    if category == "Edible Oil":
        return 0.06
    return 0.08


def apply_festival_curve(date_value: pd.Timestamp, festival_date: pd.Timestamp, peak_uplift: float) -> float:
    """Bell-shaped uplift from -10 to +5 days around festival day.

    Returns additive uplift fraction (e.g., 0.18 means +18%).
    """

    offset_days = (date_value - festival_date).days
    if offset_days < -10 or offset_days > 5:
        return 0.0

    sigma = 4.2 if offset_days <= 0 else 2.4
    bell = np.exp(-0.5 * (offset_days / sigma) ** 2)
    return peak_uplift * float(bell)


def total_festival_uplift(category: str, date_value: pd.Timestamp) -> float:
    """Combine multi-festival effects with a cap to prevent unrealistic spikes."""

    festivals = festival_calendar_2024()
    base_levels = intensity_base_uplift()
    weights = category_festival_weights()[category]

    uplift_sum = 0.0
    for festival_name, details in festivals.items():
        intensity = str(details["intensity"])
        festival_date = pd.Timestamp(details["date"])
        peak = base_levels[intensity] * weights[festival_name]
        uplift_sum += apply_festival_curve(date_value, festival_date, peak)

    # Cap cumulative uplift to keep overlapping festival effects realistic.
    return min(uplift_sum, 0.85)


def generate_sales(sku_df: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    """Generate daily sales for every SKU over calendar year 2024."""

    rng = np.random.default_rng(seed)
    dates = pd.date_range(start="2024-01-01", end="2024-12-31", freq="D")
    bounds = category_demand_bounds()

    records: list[dict[str, object]] = []

    for _, sku in sku_df.iterrows():
        category = str(sku["category"])
        min_base, max_base = bounds[category]
        base_demand = rng.uniform(min_base, max_base)

        trend_strength = rng.uniform(0.04, 0.08)
        noise_sigma = base_demand * noise_scale(category)

        for day_index, date_value in enumerate(dates):
            trend_multiplier = 1.0 + trend_strength * (day_index / (len(dates) - 1))
            weekly_multiplier = weekend_factor(category, date_value.dayofweek)
            festival_multiplier = 1.0 + total_festival_uplift(category, date_value)
            noise = rng.normal(0.0, noise_sigma)

            demand = base_demand * trend_multiplier * weekly_multiplier * festival_multiplier + noise
            units_sold = max(0, int(round(demand)))

            records.append(
                {
                    "date": date_value.strftime("%Y-%m-%d"),
                    "sku_id": sku["sku_id"],
                    "units_sold": units_sold,
                }
            )

    return pd.DataFrame(records)


def print_summary(sku_df: pd.DataFrame, sales_df: pd.DataFrame) -> None:
    """Print compact summary statistics for quick sanity checks."""

    merged = sales_df.merge(sku_df[["sku_id", "category"]], on="sku_id", how="left")

    print("\n=== Dataset Summary ===")
    print(f"SKUs: {sku_df['sku_id'].nunique()}")
    print(f"Categories: {sku_df['category'].nunique()}")
    print(f"Sales rows: {len(sales_df)}")
    print(f"Date range: {sales_df['date'].min()} to {sales_df['date'].max()}")

    category_stats = merged.groupby("category")["units_sold"].agg(["mean", "min", "max", "sum"]).round(2)
    print("\nUnits sold by category:")
    print(category_stats)


def plot_category_spike(sku_df: pd.DataFrame, sales_df: pd.DataFrame, output_path: Path, category: str = "Snacks") -> None:
    """Plot daily category demand to visualize multiple festival spikes."""

    merged = sales_df.merge(sku_df[["sku_id", "category"]], on="sku_id", how="left")
    merged["date"] = pd.to_datetime(merged["date"])

    category_daily = (
        merged.loc[merged["category"] == category]
        .groupby("date", as_index=False)["units_sold"]
        .sum()
    )

    festivals = festival_calendar_2024()

    plt.figure(figsize=(13, 5.5))
    plt.plot(category_daily["date"], category_daily["units_sold"], linewidth=1.8, color="#0b7285", label=f"{category} demand")

    for festival_name, details in festivals.items():
        fest_date = pd.Timestamp(details["date"])
        plt.axvline(fest_date, color="#c92a2a", linestyle="--", linewidth=0.9, alpha=0.55)
        plt.text(fest_date, category_daily["units_sold"].max() * 1.01, festival_name, rotation=90, fontsize=8, va="bottom")

    plt.title(f"{category} Daily Units Sold with 2024 Festival Spikes")
    plt.xlabel("Date")
    plt.ylabel("Units Sold")
    plt.ylim(bottom=0)
    plt.tight_layout()
    plt.savefig(output_path, dpi=140)
    plt.close()


def main() -> None:
    """Generate demo CSV files and a multi-festival spike plot."""

    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)

    sku_master = build_sku_master()
    sales = generate_sales(sku_master, seed=42)

    sku_path = data_dir / "demo_sku_master.csv"
    sales_path = data_dir / "demo_sales_365.csv"
    plot_path = data_dir / "demo_festival_spikes_snacks.png"

    sku_master.to_csv(sku_path, index=False)
    sales.to_csv(sales_path, index=False)

    print_summary(sku_master, sales)
    plot_category_spike(sku_master, sales, plot_path, category="Snacks")

    print("\nSaved files:")
    print(f"- {sku_path}")
    print(f"- {sales_path}")
    print(f"- {plot_path}")


if __name__ == "__main__":
    main()
