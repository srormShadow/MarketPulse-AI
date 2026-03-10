from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
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
    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    bedrock_inference_profile_id: str | None = None
    s3_data_bucket: str = Field(
        default="marketpulse-data",
        validation_alias=AliasChoices("S3_DATA_BUCKET"),
    )
    # Accept both singular/plural env names to stay compatible with existing ECS task defs.
    s3_model_bucket: str = Field(
        default="marketpulse-models",
        validation_alias=AliasChoices("S3_MODEL_BUCKET", "S3_MODELS_BUCKET"),
    )
    model_signing_key: str = ""
    allow_unsafe_model_pickle: bool = False

    # CORS — comma-separated allowed origins (empty = dev defaults only)
    frontend_url: str = ""

    # Security
    api_key: str = ""
    environment: str = "development"
    upload_max_size_mb: int = 10

    log_level: str = "INFO"
    log_format: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

    # Shopify integration
    shopify_api_key: str = ""
    shopify_api_secret: str = ""
    shopify_scopes: str = "read_products,read_orders,read_inventory"
    shopify_redirect_uri: str = ""
    shopify_api_version: str = "2024-10"
    shopify_default_cost_ratio: float = 0.6
    shopify_max_cost_ratio: float = 0.99
    shopify_api_timeout: float = 30.0

    @field_validator("debug", mode="before")
    @classmethod
    def _normalize_debug_value(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production", "0", "false", "no", "off", ""}:
                return False
            if normalized in {"1", "true", "yes", "on", "debug", "dev", "development"}:
                return True
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
