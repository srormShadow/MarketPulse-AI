from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MarketPulse AI"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    database_url: str = "sqlite:///./marketpulse.db"

    # DynamoDB backend (set USE_DYNAMO=true to activate)
    use_dynamo: bool = False
    aws_region: str = "ap-south-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    dynamo_endpoint: str | None = None
    dynamo_endpoint_url: str | None = None
    s3_endpoint: str | None = None
    s3_endpoint_url: str | None = None
    bedrock_endpoint_url: str | None = None
    mock_bedrock: bool = False
    s3_data_bucket: str = "marketpulse-data"
    s3_model_bucket: str = "marketpulse-models"

    # CORS — comma-separated allowed origins (empty = dev defaults only)
    frontend_url: str = ""

    log_level: str = "INFO"
    log_format: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
