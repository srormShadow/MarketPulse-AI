"""Tests for model diagnostics module."""

from __future__ import annotations

import pandas as pd
import pytest

from marketpulse.models.festival import Festival
from marketpulse.models.sales import Sales
from marketpulse.models.sku import SKU
from marketpulse.services.model_diagnostics import (
    analyze_category_model,
    compare_categories,
    compare_feature_sensitivity,
    rank_feature_importance,
    summarize_category_behavior,
)


def _seed_diagnostic_data(session) -> None:
    """Seed data for diagnostics tests."""
    session.add_all(
        [
            SKU(
                sku_id="DIAG_A",
                product_name="Diag A",
                category="DiagCategory",
                mrp=100.0,
                cost=50.0,
                current_inventory=200,
            ),
            SKU(
                sku_id="DIAG_B",
                product_name="Diag B",
                category="DiagCategory2",
                mrp=120.0,
                cost=60.0,
                current_inventory=150,
            ),
        ]
    )

    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    for i, dt in enumerate(dates):
        # Category 1: High festival impact
        units_a = 100 + i + (50 if dt.strftime("%m-%d") == "01-15" else 0)
        # Category 2: Low festival impact, high momentum
        units_b = 80 + (i % 7) * 5

        session.add_all(
            [
                Sales(date=dt.date(), sku_id="DIAG_A", units_sold=units_a),
                Sales(date=dt.date(), sku_id="DIAG_B", units_sold=units_b),
            ]
        )

    session.add(
        Festival(
            festival_name="TestFest",
            date=pd.Timestamp("2024-01-15").date(),
            category="general",
            historical_uplift=0.2,
        )
    )

    session.commit()


def test_analyze_category_model_returns_correct_structure(db_session, repo):
    """Test that analyze_category_model returns expected structure."""
    _seed_diagnostic_data(db_session)

    result = analyze_category_model(repo, "DiagCategory")

    assert "category" in result
    assert "coefficients" in result
    assert "intercept" in result
    assert "feature_importance" in result
    assert "n_samples" in result

    assert result["category"] == "DiagCategory"
    assert isinstance(result["coefficients"], dict)
    assert isinstance(result["intercept"], float)
    assert isinstance(result["feature_importance"], dict)
    assert isinstance(result["n_samples"], int)


def test_analyze_category_model_has_all_features(db_session, repo):
    """Test that all expected features are in coefficients."""
    _seed_diagnostic_data(db_session)

    result = analyze_category_model(repo, "DiagCategory")

    expected_features = [
        "time_index",
        "weekday",
        "festival_score",
        "lag_1",
        "lag_7",
        "rolling_mean_7",
        "rolling_std_7",
    ]

    for feature in expected_features:
        assert feature in result["coefficients"]
        assert feature in result["feature_importance"]


def test_analyze_category_model_coefficients_are_numeric(db_session, repo):
    """Test that all coefficients are numeric values."""
    _seed_diagnostic_data(db_session)

    result = analyze_category_model(repo, "DiagCategory")

    for feature, coef in result["coefficients"].items():
        assert isinstance(coef, float)
        assert not pd.isna(coef)


def test_analyze_category_model_importance_is_absolute(db_session, repo):
    """Test that feature importance is absolute value of coefficients."""
    _seed_diagnostic_data(db_session)

    result = analyze_category_model(repo, "DiagCategory")

    for feature in result["coefficients"]:
        expected_importance = abs(result["coefficients"][feature])
        actual_importance = result["feature_importance"][feature]
        assert abs(expected_importance - actual_importance) < 0.0001


def test_analyze_category_model_insufficient_data(db_session, repo):
    """Test that insufficient data raises ValueError."""
    # Add category with only 3 days of data
    db_session.add(
        SKU(
            sku_id="SPARSE",
            product_name="Sparse",
            category="SparseCategory",
            mrp=100.0,
            cost=50.0,
            current_inventory=100,
        )
    )

    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    for dt in dates:
        db_session.add(Sales(date=dt.date(), sku_id="SPARSE", units_sold=100))

    db_session.commit()

    with pytest.raises(ValueError, match="Insufficient data"):
        analyze_category_model(repo, "SparseCategory")


def test_compare_categories_returns_dataframe(db_session, repo):
    """Test that compare_categories returns a DataFrame."""
    _seed_diagnostic_data(db_session)

    result = compare_categories(repo, ["DiagCategory", "DiagCategory2"])

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2
    assert "DiagCategory" in result.index
    assert "DiagCategory2" in result.index


def test_compare_categories_has_all_features(db_session, repo):
    """Test that comparison DataFrame has all feature columns."""
    _seed_diagnostic_data(db_session)

    result = compare_categories(repo, ["DiagCategory", "DiagCategory2"])

    expected_columns = [
        "time_index",
        "weekday",
        "festival_score",
        "lag_1",
        "lag_7",
        "rolling_mean_7",
        "rolling_std_7",
        "intercept",
    ]

    for col in expected_columns:
        assert col in result.columns


def test_compare_categories_skips_invalid(db_session, repo):
    """Test that compare_categories skips categories with insufficient data."""
    _seed_diagnostic_data(db_session)

    # Should not raise error, just skip invalid category
    result = compare_categories(repo, ["DiagCategory", "NonExistent"])

    assert len(result) == 1
    assert "DiagCategory" in result.index


def test_compare_categories_empty_raises_error(repo):
    """Test that no valid categories raises ValueError."""
    with pytest.raises(ValueError, match="No categories had sufficient data"):
        compare_categories(repo, ["NonExistent1", "NonExistent2"])


def test_rank_feature_importance_returns_dataframe(db_session, repo):
    """Test that rank_feature_importance returns DataFrame."""
    _seed_diagnostic_data(db_session)

    result = rank_feature_importance(repo, ["DiagCategory", "DiagCategory2"], "festival_score")

    assert isinstance(result, pd.DataFrame)
    assert "category" in result.columns
    assert "coefficient" in result.columns
    assert "abs_coefficient" in result.columns
    assert "rank" in result.columns


def test_rank_feature_importance_sorted_by_magnitude(db_session, repo):
    """Test that ranking is sorted by absolute coefficient magnitude."""
    _seed_diagnostic_data(db_session)

    result = rank_feature_importance(repo, ["DiagCategory", "DiagCategory2"], "lag_1")

    # Check that abs_coefficient is descending
    abs_coefs = result["abs_coefficient"].tolist()
    assert abs_coefs == sorted(abs_coefs, reverse=True)

    # Check that ranks are sequential
    ranks = result["rank"].tolist()
    assert ranks == list(range(1, len(ranks) + 1))


def test_rank_feature_importance_invalid_feature(db_session, repo):
    """Test that invalid feature name returns zero coefficient."""
    _seed_diagnostic_data(db_session)

    result = rank_feature_importance(repo, ["DiagCategory"], "invalid_feature")

    # Should return result with zero coefficient for invalid feature
    assert len(result) == 1
    assert result.iloc[0]["coefficient"] == 0.0
    assert result.iloc[0]["abs_coefficient"] == 0.0


def test_summarize_category_behavior_returns_dict(db_session, repo):
    """Test that summarize_category_behavior returns dict."""
    _seed_diagnostic_data(db_session)

    result = summarize_category_behavior(repo, "DiagCategory")

    assert isinstance(result, dict)
    assert "category" in result
    assert "dominant_feature" in result
    assert "festival_sensitivity" in result
    assert "momentum_driven" in result
    assert "weekly_pattern" in result
    assert "stability" in result
    assert "summary" in result
    assert "coefficients" in result


def test_summarize_category_behavior_festival_classification(db_session, repo):
    """Test festival sensitivity classification."""
    _seed_diagnostic_data(db_session)

    result = summarize_category_behavior(repo, "DiagCategory")

    # Should be one of the valid classifications
    assert result["festival_sensitivity"] in ["high", "medium", "low"]


def test_summarize_category_behavior_momentum_boolean(db_session, repo):
    """Test that momentum_driven is boolean."""
    _seed_diagnostic_data(db_session)

    result = summarize_category_behavior(repo, "DiagCategory")

    assert isinstance(result["momentum_driven"], bool)
    assert isinstance(result["weekly_pattern"], bool)


def test_summarize_category_behavior_stability_classification(db_session, repo):
    """Test stability classification."""
    _seed_diagnostic_data(db_session)

    result = summarize_category_behavior(repo, "DiagCategory")

    assert result["stability"] in ["stable", "volatility-averse", "volatility-responsive"]


def test_summarize_category_behavior_summary_is_string(db_session, repo):
    """Test that summary is a non-empty string."""
    _seed_diagnostic_data(db_session)

    result = summarize_category_behavior(repo, "DiagCategory")

    assert isinstance(result["summary"], str)
    assert len(result["summary"]) > 0
    assert result["category"] in result["summary"]


def test_compare_feature_sensitivity_returns_dict(db_session, repo):
    """Test that compare_feature_sensitivity returns dict."""
    _seed_diagnostic_data(db_session)

    result = compare_feature_sensitivity(repo, ["DiagCategory", "DiagCategory2"])

    assert isinstance(result, dict)


def test_compare_feature_sensitivity_has_expected_keys(db_session, repo):
    """Test that result has expected feature type keys."""
    _seed_diagnostic_data(db_session)

    result = compare_feature_sensitivity(repo, ["DiagCategory", "DiagCategory2"])

    expected_keys = [
        "festival_sensitive",
        "momentum_driven",
        "weekly_seasonal",
        "trend_following",
        "volatility_aware",
    ]

    for key in expected_keys:
        assert key in result


def test_compare_feature_sensitivity_structure(db_session, repo):
    """Test that each sensitivity entry has correct structure."""
    _seed_diagnostic_data(db_session)

    result = compare_feature_sensitivity(repo, ["DiagCategory", "DiagCategory2"])

    for feature_type, data in result.items():
        assert "category" in data
        assert "coefficient" in data
        assert isinstance(data["category"], str)
        assert isinstance(data["coefficient"], float)


def test_compare_feature_sensitivity_identifies_leader(db_session, repo):
    """Test that sensitivity comparison identifies a leader for each type."""
    _seed_diagnostic_data(db_session)

    result = compare_feature_sensitivity(repo, ["DiagCategory", "DiagCategory2"])

    # Each feature type should have a leader
    for feature_type, data in result.items():
        assert data["category"] in ["DiagCategory", "DiagCategory2"]
        assert data["coefficient"] >= 0  # Should be absolute value


def test_coefficients_differ_across_categories(db_session, repo):
    """Test that different categories learn different coefficients."""
    _seed_diagnostic_data(db_session)

    comparison = compare_categories(repo, ["DiagCategory", "DiagCategory2"])

    # Check that at least some coefficients differ
    differences = []
    for col in comparison.columns:
        if col != "intercept":
            diff = abs(comparison.loc["DiagCategory", col] - comparison.loc["DiagCategory2", col])
            differences.append(diff)

    # At least one coefficient should differ by more than 0.1
    assert any(d > 0.1 for d in differences)


def test_dominant_feature_identified(db_session, repo):
    """Test that dominant feature is correctly identified."""
    _seed_diagnostic_data(db_session)

    result = analyze_category_model(repo, "DiagCategory")

    # Dominant feature should be the one with highest importance
    max_importance = max(result["feature_importance"].values())
    dominant = result["feature_importance"][result["coefficients"].keys().__iter__().__next__()]

    # Find actual dominant
    for feature, importance in result["feature_importance"].items():
        if importance == max_importance:
            dominant_feature = feature
            break

    # Should be a valid feature name
    assert dominant_feature in result["coefficients"]


def test_n_samples_reasonable(db_session, repo):
    """Test that n_samples is reasonable given input data."""
    _seed_diagnostic_data(db_session)

    result = analyze_category_model(repo, "DiagCategory")

    # We seeded 60 days, after lag features we should have ~53 samples
    assert 50 <= result["n_samples"] <= 60


def test_intercept_is_reasonable(db_session, repo):
    """Test that intercept is a reasonable value."""
    _seed_diagnostic_data(db_session)

    result = analyze_category_model(repo, "DiagCategory")

    # Intercept should be in reasonable range for our test data
    assert -1000 < result["intercept"] < 1000
    assert not pd.isna(result["intercept"])
