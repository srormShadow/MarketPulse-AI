"""Background model training for categories."""

import logging
from datetime import datetime, timezone

from marketpulse.db.repository import DataRepository
from marketpulse.infrastructure.s3 import save_model
from marketpulse.services.feature_engineering import prepare_training_data
from marketpulse.services.forecasting import train_model

logger = logging.getLogger(__name__)

def run_model_training(repo: DataRepository, category: str) -> bool:
    """Train the model for a category and save it to S3."""
    logger.info("Starting background training job for category=%s", category)
    try:
        X_train, y_train, full_df = prepare_training_data(repo, category)
        if full_df.empty or len(full_df) < 7:
            logger.warning("Insufficient historical data to train model for category=%s", category)
            return False

        model, scaler = train_model(X_train, y_train)
        
        save_model(
            model_object={
                "model": model,
                "scaler": scaler,
                "trained_at": datetime.now(timezone.utc).isoformat(),
                "feature_columns": list(X_train.columns),
            },
            category=category,
        )
        logger.info("Successfully completed background training for category=%s", category)
        return True
    except Exception:
        logger.exception("Background training failed for category=%s", category)
        return False
