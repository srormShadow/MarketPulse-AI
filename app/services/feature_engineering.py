"""Feature engineering utilities for category-level retail demand modeling."""

from __future__ import annotations

from collections.abc import Sequence
import logging

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.festival import Festival
from app.models.sales import Sales
from app.models.sku import SKU

logger = logging.getLogger(__name__)


def aggregate_category_sales(session: Session, category: str) -> pd.DataFrame:
    """Aggregate daily sales totals for a given category.

    Joins `Sales` and `SKU`, filters by category, groups by date, and returns
    a date-sorted DataFrame with columns: `date`, `units_sold`.
    """

    stmt = (
        select(Sales.date, func.sum(Sales.units_sold).label("units_sold"))
        .join(SKU, Sales.sku_id == SKU.sku_id)
        .where(SKU.category == category)
        .group_by(Sales.date)
        .order_by(Sales.date.asc())
    )

    rows = session.execute(stmt).all()
    frame = pd.DataFrame(rows, columns=["date", "units_sold"])
    if frame.empty:
        return pd.DataFrame(columns=["date", "units_sold"])

    frame["date"] = pd.to_datetime(frame["date"])
    frame["units_sold"] = pd.to_numeric(frame["units_sold"], errors="coerce")
    return frame.sort_values("date").reset_index(drop=True)


def add_time_index(df: pd.DataFrame) -> pd.DataFrame:
    """Add a sequential integer `time_index` column to the DataFrame."""

    out = df.copy()
    out["time_index"] = np.arange(len(out), dtype=int)
    return out


def add_weekday_feature(df: pd.DataFrame, one_hot_encode: bool = False) -> pd.DataFrame:
    """Add weekday-derived features.

    Adds:
    - `day_of_week` (0=Monday ... 6=Sunday)
    - `weekday` alias (same numeric value)

    If `one_hot_encode=True`, appends one-hot columns `dow_0 ... dow_6`.
    """

    out = df.copy()
    out["date"] = pd.to_datetime(out["date"])
    out["day_of_week"] = out["date"].dt.dayofweek.astype(int)
    out["weekday"] = out["day_of_week"]

    if one_hot_encode:
        encoded = pd.get_dummies(out["day_of_week"], prefix="dow", dtype=int)
        out = pd.concat([out, encoded], axis=1)

    return out


def compute_festival_proximity(
    df: pd.DataFrame,
    session: Session,
    category: str,
    k: float = 0.2,
) -> pd.DataFrame:
    """Compute multi-festival cumulative proximity score with tiered weighting.

    Design:
    - Pull all festivals from DB and project each to row-year seasonality.
    - Accumulate contributions from every relevant festival (not only nearest).
    - Use tier-based weights to preserve major/medium/minor hierarchy.
    - Apply category multipliers instead of hard binary filtering, so smaller
      festivals still create visible bumps.
    - Return bounded smooth score via `1 - exp(-sum_contrib)`.
    """

    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.sort_values("date").reset_index(drop=True)

    normalized_category = category.strip().lower()
    festival_rows = session.execute(select(Festival.festival_name, Festival.date)).all()
    logger.info(
        "Festival proximity start | category=%s | festival_rows=%s",
        normalized_category,
        len(festival_rows),
    )

    # Tiering and weighting controls event salience.
    festival_tier: dict[str, str] = {
        "diwali": "major",
        "pongal": "major",
        "eid": "medium",
        "navratri": "medium",
        "christmas": "medium",
        "holi": "minor",
        "independence day": "minor",
        "new year": "minor",
    }
    tier_weight = {"major": 1.0, "medium": 0.6, "minor": 0.3}
    tier_decay_scale = {"major": 0.70, "medium": 0.90, "minor": 1.00}
    tier_window = {"major": 32, "medium": 26, "minor": 22}

    # Category multipliers are soft weights (not hard include/exclude) so
    # medium/minor festivals remain visible.
    category_multiplier: dict[str, dict[str, float]] = {
        "edible oil": {
            "diwali": 1.00, "pongal": 0.95, "eid": 0.85, "navratri": 0.50,
            "christmas": 0.45, "holi": 0.40, "independence day": 0.35, "new year": 0.40,
        },
        "staples": {
            "diwali": 0.95, "pongal": 0.90, "eid": 0.85, "navratri": 0.55,
            "christmas": 0.45, "holi": 0.40, "independence day": 0.35, "new year": 0.40,
        },
        "snacks": {
            "diwali": 1.00, "pongal": 0.55, "eid": 0.50, "navratri": 0.75,
            "christmas": 0.85, "holi": 0.45, "independence day": 0.40, "new year": 0.50,
        },
    }
    default_category_multiplier = 0.40

    # Baseline seasonal anchors used only when festivals are missing in DB.
    baseline_month_day: dict[str, tuple[int, int]] = {
        "pongal": (1, 15),
        "holi": (3, 25),
        "eid": (4, 10),
        "independence day": (8, 15),
        "navratri": (10, 3),
        "diwali": (11, 1),
        "christmas": (12, 25),
        "new year": (12, 31),
    }

    def _candidate_dates(month: int, day: int, year: int) -> list[pd.Timestamp]:
        candidates: list[pd.Timestamp] = []
        for candidate_year in (year - 1, year, year + 1):
            try:
                candidates.append(pd.Timestamp(year=candidate_year, month=month, day=day))
            except ValueError:
                continue
        return candidates

    # Build DB month/day map and fill missing festivals from baseline map.
    db_month_day: dict[str, tuple[int, int]] = {}
    for festival_name, festival_date in festival_rows:
        normalized_name = str(festival_name).strip().lower()
        ts = pd.Timestamp(festival_date).normalize()
        db_month_day[normalized_name] = (ts.month, ts.day)

    missing_from_db = [name for name in baseline_month_day if name not in db_month_day]
    logger.info(
        "Festival DB coverage | present=%s | missing=%s",
        sorted(db_month_day.keys()),
        missing_from_db,
    )

    modeled_festivals: list[tuple[str, int, int, float, float, int, float]] = []
    for name, (fallback_month, fallback_day) in baseline_month_day.items():
        month, day = db_month_day.get(name, (fallback_month, fallback_day))
        tier = festival_tier.get(name, "minor")
        weight = tier_weight[tier]
        decay = max(0.05, k * tier_decay_scale[tier])
        window = tier_window[tier]
        cat_mult = category_multiplier.get(normalized_category, {}).get(name, default_category_multiplier)
        modeled_festivals.append((name, month, day, weight, decay, window, cat_mult))

    logger.info(
        "Festivals modeled for category=%s: %s",
        normalized_category,
        [
            f"{name}@{month:02d}-{day:02d}(w={weight:.2f},cm={cat_mult:.2f})"
            for name, month, day, weight, _, _, cat_mult in modeled_festivals
        ],
    )

    days_to_event: list[int] = []
    scores: list[float] = []

    for idx, raw_date in enumerate(out["date"]):
        if pd.isna(raw_date):
            days_to_event.append(999)
            scores.append(0.0)
            continue

        current = pd.Timestamp(raw_date).normalize()
        nearest_delta: int | None = None
        cumulative = 0.0

        for name, month, day, weight, decay, base_window, cat_mult in modeled_festivals:
            window = max(12, int(base_window))

            per_festival_deltas: list[int] = []
            for candidate in _candidate_dates(month, day, current.year):
                per_festival_deltas.append(int((candidate - current).days))
            if not per_festival_deltas:
                continue

            deltas_arr = np.array(per_festival_deltas, dtype=int)
            nearest_for_festival = int(deltas_arr[np.argmin(np.abs(deltas_arr))])

            if nearest_delta is None or abs(nearest_for_festival) < abs(nearest_delta):
                nearest_delta = nearest_for_festival

            if abs(nearest_for_festival) <= window:
                contribution = weight * cat_mult * float(np.exp(-decay * abs(nearest_for_festival)))
                cumulative += contribution

        if nearest_delta is None:
            days_to_event.append(999)
            scores.append(0.0)
        else:
            days_to_event.append(nearest_delta)
            # Smooth bounded transform avoids single-event dominance and overflow.
            scores.append(float(1.0 - np.exp(-cumulative)))

        if idx < 15:
            logger.debug(
                "Festival proximity sample | date=%s | nearest_delta=%s | cumulative=%.6f | score=%.6f",
                current.date(),
                days_to_event[-1],
                cumulative,
                scores[-1],
            )

    out["days_to_event"] = pd.Series(days_to_event, dtype=int)
    out["festival_score"] = pd.Series(scores, dtype=float)
    return out


def prepare_training_data(
    session: Session,
    category: str,
    one_hot_encode_weekday: bool = False,
    k: float = 0.2,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """Build model-ready training data for a category.

    Pipeline:
    1. Aggregate category daily demand
    2. Add time index
    3. Add weekday feature(s)
    4. Add festival proximity features
    5. Drop rows with nulls in required fields

    Returns:
    - X: feature matrix
    - y: target series (`units_sold`)
    - engineered_df: full engineered DataFrame after cleaning
    """

    aggregated = aggregate_category_sales(session, category)
    engineered = add_time_index(aggregated)
    engineered = add_weekday_feature(engineered, one_hot_encode=one_hot_encode_weekday)
    engineered = compute_festival_proximity(engineered, session, category, k=k)

    required_columns: Sequence[str] = ["time_index", "weekday", "festival_score", "units_sold"]
    engineered = engineered.dropna(subset=list(required_columns)).reset_index(drop=True)

    X = engineered[["time_index", "weekday", "festival_score"]].copy()
    y = engineered["units_sold"].astype(float)
    return X, y, engineered
