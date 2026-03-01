"""Model diagnostics for analyzing category-specific forecasting behavior.

This module provides tools to extract and compare learned coefficients from
BayesianRidge models trained on different product categories. It helps verify
that different categories learn different behavioral patterns, especially for
festival impact and lag sensitivity.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from marketpulse.services.feature_engineering import prepare_training_data
from marketpulse.services.forecasting import train_model

if TYPE_CHECKING:
    from marketpulse.db.repository import DataRepository


def analyze_category_model(repo: DataRepository, category: str) -> dict[str, Any]:
    """Analyze a trained model for a specific category.

    Trains a BayesianRidge model for the given category and extracts the learned
    coefficients, mapping them to feature names. This provides insight into which
    features the model considers most important for predicting demand.

    Args:
        repo: Active DataRepository backend.
        category: Product category name (e.g., "Snacks", "Edible Oil").

    Returns:
        Dictionary containing:
        - category: Category name
        - coefficients: Dict mapping feature names to learned coefficients
        - intercept: Model intercept (baseline prediction)
        - feature_importance: Dict with absolute coefficient values (magnitude)
        - n_samples: Number of training samples used

    Raises:
        ValueError: If category has insufficient data for training.

    Example:
        >>> result = analyze_category_model(repo, "Snacks")
        >>> print(result["coefficients"]["festival_score"])
        12.5  # Positive coefficient indicates festival boost
    """
    # Prepare training data
    X_train, y_train, full_df = prepare_training_data(repo, category)

    if X_train.empty or len(X_train) < 7:
        raise ValueError(f"Insufficient data for category '{category}'")

    # Train model
    model, scaler = train_model(X_train, y_train)

    # Extract coefficients
    feature_names = X_train.columns.tolist()
    coefficients = model.coef_

    # Map coefficients to feature names
    coef_dict = {name: float(coef) for name, coef in zip(feature_names, coefficients)}

    # Calculate feature importance (absolute magnitude)
    importance_dict = {name: abs(float(coef)) for name, coef in zip(feature_names, coefficients)}

    return {
        "category": category,
        "coefficients": coef_dict,
        "intercept": float(model.intercept_),
        "feature_importance": importance_dict,
        "n_samples": len(X_train),
    }


def compare_categories(
    repo: DataRepository,
    categories: list[str],
) -> pd.DataFrame:
    """Compare learned coefficients across multiple categories.

    Trains models for each category and collects their coefficients into a
    comparison DataFrame. This allows visual inspection of how different
    categories respond to the same features.

    Args:
        repo: Active DataRepository backend.
        categories: List of category names to compare.

    Returns:
        DataFrame where:
        - Rows are categories
        - Columns are feature names
        - Values are learned coefficients
        - Additional column 'intercept' for baseline prediction

    Example:
        >>> df = compare_categories(session, ["Snacks", "Edible Oil", "Staples"])
        >>> print(df["festival_score"])
        Snacks        15.2
        Edible Oil    22.8
        Staples       18.5
    """
    results = []

    for category in categories:
        try:
            analysis = analyze_category_model(repo, category)
            row = {"category": category}
            row.update(analysis["coefficients"])
            row["intercept"] = analysis["intercept"]
            results.append(row)
        except ValueError as e:
            print(f"Warning: Skipping {category} - {e}")
            continue

    if not results:
        raise ValueError("No categories had sufficient data for comparison")

    df = pd.DataFrame(results)
    df = df.set_index("category")
    return df


def rank_feature_importance(
    repo: DataRepository,
    categories: list[str],
    feature: str,
) -> pd.DataFrame:
    """Rank categories by importance of a specific feature.

    Args:
        repo: Active DataRepository backend.
        categories: List of category names to compare.
        feature: Feature name to rank by (e.g., "festival_score", "lag_1").

    Returns:
        DataFrame with columns:
        - category: Category name
        - coefficient: Learned coefficient for the feature
        - abs_coefficient: Absolute value (magnitude)
        - rank: Rank by absolute magnitude (1 = highest)

    Example:
        >>> df = rank_feature_importance(session, categories, "festival_score")
        >>> print(df.head())
                    category  coefficient  abs_coefficient  rank
        0       Edible Oil         22.8             22.8     1
        1          Staples         18.5             18.5     2
        2           Snacks         15.2             15.2     3
    """
    results = []

    for category in categories:
        try:
            analysis = analyze_category_model(repo, category)
            coef = analysis["coefficients"].get(feature, 0.0)
            results.append(
                {
                    "category": category,
                    "coefficient": coef,
                    "abs_coefficient": abs(coef),
                }
            )
        except ValueError:
            continue

    if not results:
        raise ValueError(f"No categories had data for feature '{feature}'")

    df = pd.DataFrame(results)
    df = df.sort_values("abs_coefficient", ascending=False).reset_index(drop=True)
    df["rank"] = range(1, len(df) + 1)

    return df


def summarize_category_behavior(repo: DataRepository, category: str) -> dict[str, Any]:
    """Generate a behavioral summary for a category's model.

    Analyzes the trained model and provides human-readable insights about
    the category's demand patterns.

    Args:
        repo: Active DataRepository backend.
        category: Product category name.

    Returns:
        Dictionary containing:
        - category: Category name
        - dominant_feature: Feature with highest absolute coefficient
        - festival_sensitivity: Classification (high/medium/low)
        - momentum_driven: Whether lag_1 is significant
        - weekly_pattern: Whether lag_7 is significant
        - stability: Based on rolling_std_7 coefficient
        - summary: Human-readable description

    Example:
        >>> summary = summarize_category_behavior(session, "Snacks")
        >>> print(summary["summary"])
        "Snacks is highly festival-sensitive with strong momentum effects"
    """
    analysis = analyze_category_model(repo, category)
    coefs = analysis["coefficients"]
    importance = analysis["feature_importance"]

    # Find dominant feature
    dominant_feature = max(importance.items(), key=lambda x: x[1])[0]

    # Classify festival sensitivity
    festival_coef = abs(coefs.get("festival_score", 0.0))
    if festival_coef > 15:
        festival_sensitivity = "high"
    elif festival_coef > 8:
        festival_sensitivity = "medium"
    else:
        festival_sensitivity = "low"

    # Check momentum (lag_1)
    lag_1_coef = abs(coefs.get("lag_1", 0.0))
    momentum_driven = lag_1_coef > 0.1

    # Check weekly pattern (lag_7)
    lag_7_coef = abs(coefs.get("lag_7", 0.0))
    weekly_pattern = lag_7_coef > 0.05

    # Check stability (rolling_std_7 - negative means volatility reduces prediction)
    std_coef = coefs.get("rolling_std_7", 0.0)
    if abs(std_coef) < 0.1:
        stability = "stable"
    elif std_coef < 0:
        stability = "volatility-averse"
    else:
        stability = "volatility-responsive"

    # Generate summary
    summary_parts = [f"{category} is"]

    if festival_sensitivity == "high":
        summary_parts.append("highly festival-sensitive")
    elif festival_sensitivity == "medium":
        summary_parts.append("moderately festival-sensitive")
    else:
        summary_parts.append("festival-independent")

    if momentum_driven:
        summary_parts.append("with strong momentum effects")
    elif weekly_pattern:
        summary_parts.append("with weekly seasonality")
    else:
        summary_parts.append("with stable demand patterns")

    summary = " ".join(summary_parts)

    return {
        "category": category,
        "dominant_feature": dominant_feature,
        "festival_sensitivity": festival_sensitivity,
        "momentum_driven": momentum_driven,
        "weekly_pattern": weekly_pattern,
        "stability": stability,
        "summary": summary,
        "coefficients": coefs,
    }


def compare_feature_sensitivity(
    repo: DataRepository,
    categories: list[str],
) -> dict[str, dict[str, str]]:
    """Compare feature sensitivity across categories.

    Identifies which category is most sensitive to each feature type.

    Args:
        repo: Active DataRepository backend.
        categories: List of category names to compare.

    Returns:
        Dictionary mapping feature types to category rankings:
        - festival_sensitive: Category most affected by festivals
        - momentum_driven: Category most affected by recent demand
        - weekly_seasonal: Category most affected by weekly patterns
        - trend_following: Category most affected by time trend
        - volatility_aware: Category most affected by demand volatility

    Example:
        >>> result = compare_feature_sensitivity(session, categories)
        >>> print(result["festival_sensitive"])
        {"category": "Edible Oil", "coefficient": 22.8}
    """
    # Collect all analyses
    analyses = {}
    for category in categories:
        try:
            analyses[category] = analyze_category_model(repo, category)
        except ValueError:
            continue

    if not analyses:
        raise ValueError("No categories had sufficient data")

    # Find most sensitive for each feature type
    results = {}

    # Festival sensitivity
    festival_scores = {
        cat: abs(data["coefficients"].get("festival_score", 0.0))
        for cat, data in analyses.items()
    }
    if festival_scores:
        top_cat = max(festival_scores.items(), key=lambda x: x[1])
        results["festival_sensitive"] = {"category": top_cat[0], "coefficient": top_cat[1]}

    # Momentum (lag_1)
    lag_1_scores = {
        cat: abs(data["coefficients"].get("lag_1", 0.0)) for cat, data in analyses.items()
    }
    if lag_1_scores:
        top_cat = max(lag_1_scores.items(), key=lambda x: x[1])
        results["momentum_driven"] = {"category": top_cat[0], "coefficient": top_cat[1]}

    # Weekly seasonality (lag_7)
    lag_7_scores = {
        cat: abs(data["coefficients"].get("lag_7", 0.0)) for cat, data in analyses.items()
    }
    if lag_7_scores:
        top_cat = max(lag_7_scores.items(), key=lambda x: x[1])
        results["weekly_seasonal"] = {"category": top_cat[0], "coefficient": top_cat[1]}

    # Trend following (time_index)
    time_scores = {
        cat: abs(data["coefficients"].get("time_index", 0.0)) for cat, data in analyses.items()
    }
    if time_scores:
        top_cat = max(time_scores.items(), key=lambda x: x[1])
        results["trend_following"] = {"category": top_cat[0], "coefficient": top_cat[1]}

    # Volatility awareness (rolling_std_7)
    std_scores = {
        cat: abs(data["coefficients"].get("rolling_std_7", 0.0)) for cat, data in analyses.items()
    }
    if std_scores:
        top_cat = max(std_scores.items(), key=lambda x: x[1])
        results["volatility_aware"] = {"category": top_cat[0], "coefficient": top_cat[1]}

    return results
