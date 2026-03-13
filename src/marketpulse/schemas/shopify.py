"""Pydantic schemas for Shopify integration API."""

from pydantic import BaseModel, Field


class ShopifyInstallRequest(BaseModel):
    """Request to initiate Shopify OAuth flow."""

    shop_domain: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Shopify store domain (e.g., my-store.myshopify.com)",
    )


class ShopifyInstallResponse(BaseModel):
    """Response containing the Shopify OAuth authorization URL."""

    authorization_url: str = Field(description="Redirect URL for Shopify OAuth consent")


class ShopifyStoreResponse(BaseModel):
    """Public representation of a connected Shopify store."""

    id: int
    organization_id: int | None = None
    shop_domain: str
    scope: str
    is_active: bool
    installed_at: str | None = None
    last_synced_at: str | None = None


class ShopifyStoreListResponse(BaseModel):
    """List of connected Shopify stores."""

    stores: list[ShopifyStoreResponse]
    total: int


class ShopifySyncRequest(BaseModel):
    """Request to trigger a manual Shopify data sync."""

    sync_products: bool = Field(default=True, description="Sync products and inventory")
    sync_orders: bool = Field(default=True, description="Sync orders as sales data")
    orders_days_back: int = Field(default=90, ge=1, le=365, description="How many days of order history to sync")


class ShopifySyncResponse(BaseModel):
    """Response from a Shopify sync operation."""

    status: str = "completed"
    store_id: int
    shop_domain: str
    products_synced: int = 0
    orders_synced: int = 0
    skus_created: int = 0
    sales_records_created: int = 0
