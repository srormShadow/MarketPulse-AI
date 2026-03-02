"""Read-only debug schemas for internal data inspection."""

from datetime import date

from pydantic import BaseModel, Field


class SKUItemResponse(BaseModel):
    """Serialized SKU record for debug listings."""

    sku_id: str
    product_name: str
    category: str
    mrp: float
    cost: float
    current_inventory: int


class SKUListResponse(BaseModel):
    """Paginated SKU list payload."""

    status: str = "success"
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    items: list[SKUItemResponse]


class SalesCountResponse(BaseModel):
    """Total sales row count payload."""

    status: str = "success"
    total_sales_rows: int = Field(ge=0)


class FestivalItemResponse(BaseModel):
    """Serialized festival record."""

    festival_name: str
    date: date
    category: str
    categories: list[str] = Field(default_factory=list)
    historical_uplift: float
    demand_multiplier: float = 1.0
    days_until: int = 0


class FestivalListResponse(BaseModel):
    """Festival list payload."""

    status: str = "success"
    total: int = Field(ge=0)
    items: list[FestivalItemResponse]
