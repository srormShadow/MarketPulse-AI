"""Generate a realistic synthetic retail dataset for one store.

Improvements over v1:
- 2025 calendar year (aligns closer to 2026 festival seed for forecasting)
- Autocorrelated demand (AR(1) noise for day-to-day stickiness)
- Per-weekday demand profiles (not just weekend/weekday binary)
- Monthly seasonality (summer, monsoon, winter patterns per category)
- Asymmetric festival curves (slow ramp-up, sharp post-festival drop)
- Category-specific festival shapes (snacks peak earlier, staples peak later)
- Random promotional events (occasional 1-3 day spikes unrelated to festivals)
- Occasional supply disruptions (random demand dips)
- Year-over-year festival jitter (festivals dont hit identically each time)

Outputs:
- data/demo_sku_master.csv
- data/demo_sales_365.csv
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# SKU Master
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Category-specific base demand
# ---------------------------------------------------------------------------

CATEGORY_PROFILES = {
    "Edible Oil": {
        "base_range": (85, 125),
        # Per-weekday multipliers (Mon=0 .. Sun=6)
        # Oil: steady weekdays, slight weekend bump for cooking
        "weekday_pattern": [0.96, 0.97, 1.00, 1.01, 1.03, 1.08, 1.05],
        # Monthly seasonality: winter cooking boost, monsoon dip
        "monthly_seasonality": [1.08, 1.04, 1.00, 0.96, 0.93, 0.90, 0.88, 0.91, 0.95, 1.02, 1.10, 1.12],
        "noise_base": 0.07,
        "ar_coeff": 0.35,       # autocorrelation strength
        "trend_range": (0.03, 0.06),
        "promo_freq": 0.02,     # 2% of days get random promos
        "promo_boost": (0.12, 0.25),
        "disruption_freq": 0.008,
        "disruption_dip": (0.15, 0.30),
    },
    "Staples": {
        "base_range": (45, 75),
        # Staples: month-start spike (salary day buying), mid-week restocking
        "weekday_pattern": [1.05, 1.02, 0.98, 0.97, 1.00, 1.04, 1.02],
        # Monsoon/rainy season bump for staples (stocking up)
        "monthly_seasonality": [1.02, 1.00, 0.97, 0.95, 0.93, 0.96, 1.05, 1.08, 1.04, 1.00, 1.06, 1.10],
        "noise_base": 0.09,
        "ar_coeff": 0.40,
        "trend_range": (0.02, 0.05),
        "promo_freq": 0.015,
        "promo_boost": (0.10, 0.20),
        "disruption_freq": 0.01,
        "disruption_dip": (0.20, 0.40),
    },
    "Snacks": {
        "base_range": (105, 160),
        # Snacks: big weekend spike, Friday evening start, Monday dip
        "weekday_pattern": [0.88, 0.92, 0.95, 0.98, 1.08, 1.22, 1.18],
        # Summer heat boosts beverages/snacks, winter party season
        "monthly_seasonality": [0.95, 0.97, 1.02, 1.08, 1.12, 1.06, 0.94, 0.92, 0.96, 1.00, 1.10, 1.15],
        "noise_base": 0.10,
        "ar_coeff": 0.30,
        "trend_range": (0.05, 0.10),
        "promo_freq": 0.03,
        "promo_boost": (0.15, 0.35),
        "disruption_freq": 0.005,
        "disruption_dip": (0.10, 0.25),
    },
}


# ---------------------------------------------------------------------------
# 2025 Festival Calendar with category-specific impacts
# ---------------------------------------------------------------------------

FESTIVAL_CALENDAR_2025 = {
    "Pongal": {
        "date": pd.Timestamp("2025-01-14"),
        "impacts": {"Edible Oil": 0.40, "Staples": 0.35, "Snacks": 0.20},
        "ramp_days": 8, "decay_days": 3,
    },
    "Republic Day": {
        "date": pd.Timestamp("2025-01-26"),
        "impacts": {"Edible Oil": 0.05, "Staples": 0.08, "Snacks": 0.18},
        "ramp_days": 3, "decay_days": 1,
    },
    "Holi": {
        "date": pd.Timestamp("2025-03-14"),
        "impacts": {"Edible Oil": 0.15, "Staples": 0.12, "Snacks": 0.45},
        "ramp_days": 7, "decay_days": 2,
    },
    "Eid ul-Fitr": {
        "date": pd.Timestamp("2025-03-31"),
        "impacts": {"Edible Oil": 0.38, "Staples": 0.42, "Snacks": 0.22},
        "ramp_days": 10, "decay_days": 3,
    },
    "Ram Navami": {
        "date": pd.Timestamp("2025-04-06"),
        "impacts": {"Edible Oil": 0.12, "Staples": 0.20, "Snacks": 0.10},
        "ramp_days": 5, "decay_days": 2,
    },
    "Independence Day": {
        "date": pd.Timestamp("2025-08-15"),
        "impacts": {"Edible Oil": 0.06, "Staples": 0.08, "Snacks": 0.22},
        "ramp_days": 3, "decay_days": 1,
    },
    "Raksha Bandhan": {
        "date": pd.Timestamp("2025-08-09"),
        "impacts": {"Edible Oil": 0.10, "Staples": 0.12, "Snacks": 0.35},
        "ramp_days": 6, "decay_days": 2,
    },
    "Janmashtami": {
        "date": pd.Timestamp("2025-08-16"),
        "impacts": {"Edible Oil": 0.18, "Staples": 0.15, "Snacks": 0.12},
        "ramp_days": 5, "decay_days": 2,
    },
    "Ganesh Chaturthi": {
        "date": pd.Timestamp("2025-09-07"),
        "impacts": {"Edible Oil": 0.15, "Staples": 0.20, "Snacks": 0.38},
        "ramp_days": 8, "decay_days": 4,
    },
    "Navratri Start": {
        "date": pd.Timestamp("2025-10-02"),
        "impacts": {"Edible Oil": 0.25, "Staples": 0.30, "Snacks": 0.20},
        "ramp_days": 10, "decay_days": 2,  # 9-day festival, sustained
    },
    "Dussehra": {
        "date": pd.Timestamp("2025-10-12"),
        "impacts": {"Edible Oil": 0.18, "Staples": 0.22, "Snacks": 0.30},
        "ramp_days": 5, "decay_days": 2,
    },
    "Dhanteras": {
        "date": pd.Timestamp("2025-10-29"),
        "impacts": {"Edible Oil": 0.30, "Staples": 0.25, "Snacks": 0.35},
        "ramp_days": 5, "decay_days": 1,
    },
    "Diwali": {
        "date": pd.Timestamp("2025-10-31"),
        "impacts": {"Edible Oil": 0.55, "Staples": 0.45, "Snacks": 0.65},
        "ramp_days": 14, "decay_days": 4,
    },
    "Bhai Dooj": {
        "date": pd.Timestamp("2025-11-02"),
        "impacts": {"Edible Oil": 0.08, "Staples": 0.06, "Snacks": 0.25},
        "ramp_days": 2, "decay_days": 1,
    },
    "Christmas": {
        "date": pd.Timestamp("2025-12-25"),
        "impacts": {"Edible Oil": 0.12, "Staples": 0.10, "Snacks": 0.30},
        "ramp_days": 7, "decay_days": 2,
    },
    "New Year": {
        "date": pd.Timestamp("2025-12-31"),
        "impacts": {"Edible Oil": 0.10, "Staples": 0.08, "Snacks": 0.28},
        "ramp_days": 4, "decay_days": 1,
    },
}


# ---------------------------------------------------------------------------
# Festival uplift curve (asymmetric: gradual ramp, sharp drop)
# ---------------------------------------------------------------------------

def festival_uplift_on_day(
    date_value: pd.Timestamp,
    festival_date: pd.Timestamp,
    peak_uplift: float,
    ramp_days: int,
    decay_days: int,
    rng: np.random.Generator,
) -> float:
    """Asymmetric festival effect with per-instance jitter.

    Before festival: gradual ramp using squared cosine (slow start, accelerating)
    After festival: sharp exponential decay
    Peak jitter: +/- 10% randomness on each festival instance
    """
    offset = (date_value - festival_date).days

    if offset < -ramp_days or offset > decay_days + 2:
        return 0.0

    # Add jitter to peak so festivals aren't identical each time
    jittered_peak = peak_uplift * rng.uniform(0.88, 1.12)

    if offset <= 0:
        # Ramp-up: squared cosine for natural acceleration
        progress = 1.0 - abs(offset) / ramp_days
        curve = progress ** 1.8  # slightly sub-quadratic
        return jittered_peak * curve
    else:
        # Post-festival: fast exponential decay
        tau = max(0.8, decay_days / 2.5)
        return jittered_peak * np.exp(-offset / tau)


def total_festival_uplift(
    category: str,
    date_value: pd.Timestamp,
    rng: np.random.Generator,
) -> float:
    """Combine all festival effects for a given date and category."""
    uplift = 0.0
    for _name, details in FESTIVAL_CALENDAR_2025.items():
        peak = details["impacts"].get(category, 0.0)
        if peak <= 0:
            continue
        uplift += festival_uplift_on_day(
            date_value,
            details["date"],
            peak,
            details["ramp_days"],
            details["decay_days"],
            rng,
        )
    return min(uplift, 0.90)


# ---------------------------------------------------------------------------
# Month-start salary-day effect (common in Indian retail)
# ---------------------------------------------------------------------------

def salary_day_boost(day_of_month: int, category: str) -> float:
    """Salary-day effect: demand bumps on 1st-5th and 28th-31st of month."""
    if category == "Snacks":
        # Snacks less affected by salary cycles
        boost_map = {1: 1.04, 2: 1.03, 3: 1.02, 28: 1.02, 29: 1.03, 30: 1.04, 31: 1.03}
    else:
        # Staples and oil: strong salary-day stocking
        boost_map = {1: 1.12, 2: 1.10, 3: 1.06, 4: 1.03, 28: 1.03, 29: 1.05, 30: 1.08, 31: 1.06}
    return boost_map.get(day_of_month, 1.0)


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------

def generate_sales(sku_df: pd.DataFrame, seed: int = 2025) -> pd.DataFrame:
    """Generate daily sales for every SKU over calendar year 2025.

    Key realism improvements:
    - AR(1) autocorrelated noise (demand sticks day-to-day)
    - Per-weekday patterns (not binary weekend/weekday)
    - Monthly seasonality curves per category
    - Asymmetric festival curves with jitter
    - Random promotional events
    - Occasional supply disruptions
    - Salary-day effects
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start="2025-01-01", end="2025-12-31", freq="D")
    n_days = len(dates)

    records: list[dict[str, object]] = []

    for _, sku in sku_df.iterrows():
        category = str(sku["category"])
        profile = CATEGORY_PROFILES[category]

        # Random base demand for this SKU within category range
        lo, hi = profile["base_range"]
        base_demand = rng.uniform(lo, hi)

        # Random trend strength
        trend_lo, trend_hi = profile["trend_range"]
        trend_strength = rng.uniform(trend_lo, trend_hi)

        # Pre-generate AR(1) noise series for this SKU
        ar_coeff = profile["ar_coeff"]
        noise_std = base_demand * profile["noise_base"]
        ar_noise = np.zeros(n_days)
        ar_noise[0] = rng.normal(0, noise_std)
        for t in range(1, n_days):
            ar_noise[t] = ar_coeff * ar_noise[t - 1] + rng.normal(0, noise_std * np.sqrt(1 - ar_coeff ** 2))

        # Pre-generate random promo and disruption days
        promo_mask = rng.random(n_days) < profile["promo_freq"]
        disruption_mask = rng.random(n_days) < profile["disruption_freq"]

        for day_idx, date_value in enumerate(dates):
            # 1) Linear trend
            trend_mult = 1.0 + trend_strength * (day_idx / (n_days - 1))

            # 2) Per-weekday seasonal pattern
            weekday_mult = profile["weekday_pattern"][date_value.dayofweek]

            # 3) Monthly seasonality
            month_mult = profile["monthly_seasonality"][date_value.month - 1]

            # 4) Festival uplift (asymmetric with jitter)
            festival_mult = 1.0 + total_festival_uplift(category, date_value, rng)

            # 5) Salary-day effect
            salary_mult = salary_day_boost(date_value.day, category)

            # 6) Random promotional events (1-3 day bursts)
            promo_mult = 1.0
            if promo_mask[day_idx]:
                promo_lo, promo_hi = profile["promo_boost"]
                promo_mult = 1.0 + rng.uniform(promo_lo, promo_hi)

            # 7) Supply disruptions (demand dips)
            disruption_mult = 1.0
            if disruption_mask[day_idx]:
                dip_lo, dip_hi = profile["disruption_dip"]
                disruption_mult = 1.0 - rng.uniform(dip_lo, dip_hi)

            # Combine all multiplicative effects
            demand = (
                base_demand
                * trend_mult
                * weekday_mult
                * month_mult
                * festival_mult
                * salary_mult
                * promo_mult
                * disruption_mult
            )

            # Add autocorrelated noise
            demand += ar_noise[day_idx]

            units_sold = max(0, int(round(demand)))

            records.append({
                "date": date_value.strftime("%Y-%m-%d"),
                "sku_id": sku["sku_id"],
                "units_sold": units_sold,
            })

    return pd.DataFrame(records)


def print_summary(sku_df: pd.DataFrame, sales_df: pd.DataFrame) -> None:
    """Print compact summary statistics for quick sanity checks."""
    merged = sales_df.merge(sku_df[["sku_id", "category"]], on="sku_id", how="left")

    print("\n=== Dataset Summary ===")
    print(f"SKUs: {sku_df['sku_id'].nunique()}")
    print(f"Categories: {sku_df['category'].nunique()}")
    print(f"Sales rows: {len(sales_df)}")
    print(f"Date range: {sales_df['date'].min()} to {sales_df['date'].max()}")

    category_stats = merged.groupby("category")["units_sold"].agg(["mean", "min", "max", "std", "sum"]).round(2)
    print("\nUnits sold by category:")
    print(category_stats)

    # Show coefficient of variation (realism indicator)
    print("\nCoefficient of variation by category (higher = more realistic variability):")
    for cat in sorted(merged["category"].unique()):
        cat_data = merged.loc[merged["category"] == cat, "units_sold"]
        cv = cat_data.std() / cat_data.mean() * 100
        print(f"  {cat}: {cv:.1f}%")


def main() -> None:
    """Generate demo CSV files."""
    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)

    sku_master = build_sku_master()
    sales = generate_sales(sku_master, seed=2025)

    sku_path = data_dir / "demo_sku_master.csv"
    sales_path = data_dir / "demo_sales_365.csv"

    sku_master.to_csv(sku_path, index=False)
    sales.to_csv(sales_path, index=False)

    print_summary(sku_master, sales)

    print("\nSaved files:")
    print(f"- {sku_path}")
    print(f"- {sales_path}")


if __name__ == "__main__":
    main()
