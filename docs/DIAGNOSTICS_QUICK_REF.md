# Model Diagnostics - Quick Reference

## Quick Start

```python
from app.services.model_diagnostics import (
    analyze_category_model,
    compare_categories,
    summarize_category_behavior
)
from app.db.session import SessionLocal

session = SessionLocal()
```

## 1. Analyze Single Category

```python
result = analyze_category_model(session, "Snacks")

print(f"Festival coefficient: {result['coefficients']['festival_score']}")
print(f"Momentum coefficient: {result['coefficients']['lag_1']}")
print(f"Dominant feature: {max(result['feature_importance'].items(), key=lambda x: x[1])[0]}")
```

## 2. Compare Multiple Categories

```python
categories = ["Snacks", "Edible Oil", "Staples"]
comparison = compare_categories(session, categories)

print(comparison)
# Shows side-by-side coefficient comparison
```

## 3. Rank by Feature

```python
from app.services.model_diagnostics import rank_feature_importance

ranking = rank_feature_importance(session, categories, "festival_score")
print(ranking)
# Shows which category is most festival-sensitive
```

## 4. Get Behavioral Summary

```python
summary = summarize_category_behavior(session, "Snacks")

print(summary["summary"])
# Human-readable description
```

## 5. Find Sensitivity Leaders

```python
from app.services.model_diagnostics import compare_feature_sensitivity

leaders = compare_feature_sensitivity(session, categories)

print(f"Most festival-sensitive: {leaders['festival_sensitive']['category']}")
print(f"Most momentum-driven: {leaders['momentum_driven']['category']}")
```

## Run Verification

```bash
python verify_category_behavior.py
```

## Run Tests

```bash
# Diagnostics tests only
pytest tests/test_model_diagnostics.py -v

# All tests
pytest tests/ -v
```

## Coefficient Interpretation

| Coefficient | Meaning |
|-------------|---------|
| **Positive festival_score** | Festivals increase demand |
| **Positive lag_1** | Momentum effect (recent demand predicts future) |
| **Positive lag_7** | Weekly seasonality |
| **Negative lag_7** | Inverse weekly pattern |
| **Positive rolling_mean_7** | Recent average predicts future |
| **Positive rolling_std_7** | Volatility increases predictions |
| **Negative rolling_std_7** | Volatility decreases predictions |

## Magnitude Guide

- **>10**: Strong influence
- **5-10**: Moderate influence
- **<5**: Weak influence

## Common Use Cases

### Find Most Festival-Sensitive Category

```python
ranking = rank_feature_importance(session, categories, "festival_score")
top = ranking.iloc[0]["category"]
print(f"Focus festival promotions on: {top}")
```

### Identify Momentum-Based Categories

```python
ranking = rank_feature_importance(session, categories, "lag_1")
momentum = ranking[ranking["abs_coefficient"] > 0.1]["category"].tolist()
print(f"Use momentum inventory for: {momentum}")
```

### Validate Model Learning

```python
comparison = compare_categories(session, categories)
variance = comparison["festival_score"].var()
if variance > 1.0:
    print("✓ Models learn distinct patterns")
```

## Files

- **Module**: `app/services/model_diagnostics.py`
- **Verification**: `verify_category_behavior.py`
- **Tests**: `tests/test_model_diagnostics.py`
- **Docs**: `docs/MODEL_DIAGNOSTICS.md`

## Test Status

✅ 117 tests passing (92 existing + 25 new)

## Documentation

See `docs/MODEL_DIAGNOSTICS.md` for complete documentation.
