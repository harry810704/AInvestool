"""
Data models for the Investment Dashboard.

This module defines Pydantic models for type-safe data structures
used throughout the application.
"""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict


class Asset(BaseModel):
    """
    Represents a single investment asset in the portfolio.
    
    Attributes:
        type: Asset category (e.g., "美股", "台股", "虛擬貨幣", "稀有金屬")
        ticker: Stock ticker symbol (e.g., "AAPL", "2330.TW")
        quantity: Number of shares/units held
        avg_cost: Average cost per share/unit
        currency: Currency of the asset (USD or TWD)
        manual_price: Manually set price (0.0 if using live data)
        last_update: Last price update timestamp (ISO format or "N/A")
    """
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )
    
    type: str = Field(..., description="Asset category")
    ticker: str = Field(..., description="Stock ticker symbol", min_length=1)
    quantity: float = Field(..., ge=0, description="Number of shares/units")
    avg_cost: float = Field(..., ge=0, description="Average cost per share")
    currency: Literal["USD", "TWD"] = Field(default="USD", description="Asset currency")
    manual_price: float = Field(default=0.0, ge=0, description="Manual price override")
    last_update: str = Field(default="N/A", description="Last update timestamp")
    suggested_sl: Optional[float] = Field(default=None, description="Suggested stop loss price")
    suggested_tp: Optional[float] = Field(default=None, description="Suggested take profit price")
    
    @field_validator('ticker')
    @classmethod
    def ticker_uppercase(cls, v: str) -> str:
        """Ensure ticker is uppercase."""
        return v.upper()
    
    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate asset type against known categories."""
        valid_types = ["美股", "台股", "虛擬貨幣", "稀有金屬"]
        if v not in valid_types:
            # Allow custom types but warn
            import warnings
            warnings.warn(f"Asset type '{v}' is not in standard types: {valid_types}")
        return v
    
    def to_dict(self) -> dict:
        """
        Convert to dictionary for CSV serialization.
        
        Returns:
            dict: Dictionary with capitalized keys matching CSV format
        """
        return {
            "Type": self.type,
            "Ticker": self.ticker,
            "Quantity": self.quantity,
            "Avg_Cost": self.avg_cost,
            "Currency": self.currency,
            "Manual_Price": self.manual_price,
            "Last_Update": self.last_update,
            "Suggested_SL": self.suggested_sl if self.suggested_sl is not None else "",
            "Suggested_TP": self.suggested_tp if self.suggested_tp is not None else "",
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Asset":
        """
        Create Asset from dictionary (e.g., from CSV).
        
        Args:
            data: Dictionary with asset data
            
        Returns:
            Asset: Validated asset instance
        """
        # Handle both capitalized (CSV) and lowercase (internal) keys
        # Helper to parse optional float fields
        def parse_optional_float(key1: str, key2: str) -> Optional[float]:
            val = data.get(key1) or data.get(key2)
            if val is None or val == "" or val == "N/A":
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None
        
        return cls(
            type=data.get("Type") or data.get("type"),
            ticker=data.get("Ticker") or data.get("ticker"),
            quantity=float(data.get("Quantity") or data.get("quantity", 0)),
            avg_cost=float(data.get("Avg_Cost") or data.get("avg_cost", 0)),
            currency=data.get("Currency") or data.get("currency", "USD"),
            manual_price=float(data.get("Manual_Price") or data.get("manual_price", 0)),
            last_update=data.get("Last_Update") or data.get("last_update", "N/A"),
            suggested_sl=parse_optional_float("Suggested_SL", "suggested_sl"),
            suggested_tp=parse_optional_float("Suggested_TP", "suggested_tp"),
        )


class MarketData(BaseModel):
    """
    Market data for a single asset.
    
    Attributes:
        ticker: Stock ticker symbol
        type: Asset category
        quantity: Number of shares
        current_price: Current market price
        market_value: Total market value (price * quantity)
        total_cost: Total cost basis
        unrealized_pl: Unrealized profit/loss
        roi_pct: Return on investment percentage
        daily_change_pct: Daily price change percentage
        status: Data status indicator
        avg_cost: Average cost per share
        currency: Asset currency
    """
    
    model_config = ConfigDict(validate_assignment=True)
    
    type: str
    ticker: str
    quantity: float
    current_price: float
    market_value: float
    total_cost: float
    unrealized_pl: float
    roi_pct: float
    daily_change_pct: float = 0.0
    status: str = "⚠️ 待更新"
    avg_cost: float
    currency: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary for DataFrame."""
        return {
            "Type": self.type,
            "Ticker": self.ticker,
            "Quantity": self.quantity,
            "Current_Price": self.current_price,
            "Market_Value": self.market_value,
            "Total_Cost": self.total_cost,
            "Unrealized_PL": self.unrealized_pl,
            "ROI (%)": self.roi_pct,
            "Daily_Change (%)": self.daily_change_pct,
            "Status": self.status,
            "Avg_Cost": self.avg_cost,
            "Currency": self.currency,
        }


class AllocationSettings(BaseModel):
    """
    Investment allocation target settings.
    
    Attributes:
        targets: Dictionary mapping asset types to target percentages
    """
    
    model_config = ConfigDict(validate_assignment=True)
    
    targets: dict[str, float] = Field(
        default_factory=lambda: {
            "美股": 40.0,
            "台股": 40.0,
            "虛擬貨幣": 10.0,
            "稀有金屬": 10.0,
        }
    )
    
    @field_validator('targets')
    @classmethod
    def validate_percentages(cls, v: dict[str, float]) -> dict[str, float]:
        """Validate that all percentages are non-negative."""
        for asset_type, pct in v.items():
            if pct < 0:
                raise ValueError(f"Percentage for {asset_type} cannot be negative")
            if pct > 100:
                raise ValueError(f"Percentage for {asset_type} cannot exceed 100%")
        return v
    
    def total_percentage(self) -> float:
        """Calculate total allocation percentage."""
        return sum(self.targets.values())
    
    def is_valid(self) -> bool:
        """Check if allocation is valid (sums to ~100%)."""
        total = self.total_percentage()
        return abs(total - 100.0) < 0.01
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return self.targets


class PriceUpdate(BaseModel):
    """
    Result of a price update operation.
    
    Attributes:
        ticker: Stock ticker symbol
        success: Whether the update succeeded
        price: Updated price (if successful)
        error: Error message (if failed)
        timestamp: Update timestamp
    """
    
    model_config = ConfigDict(validate_assignment=True)
    
    ticker: str
    success: bool
    price: Optional[float] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class DeploymentAction(BaseModel):
    """
    Represents a planned investment action.
    
    Attributes:
        type: Asset category
        ticker: Stock ticker symbol
        price: Purchase price per share
        qty: Quantity to purchase
        total: Total investment amount
        is_new: Whether this is a new asset (vs. adding to existing)
    """
    
    model_config = ConfigDict(validate_assignment=True)
    
    type: str
    ticker: str
    price: float = Field(gt=0, description="Price per share")
    qty: float = Field(gt=0, description="Quantity to purchase")
    total: float = Field(gt=0, description="Total investment")
    is_new: bool = Field(default=False, description="Is new asset")
    
    @field_validator('total')
    @classmethod
    def validate_total(cls, v: float, info) -> float:
        """Validate that total matches price * qty."""
        if 'price' in info.data and 'qty' in info.data:
            expected = info.data['price'] * info.data['qty']
            if abs(v - expected) > 0.01:
                raise ValueError(f"Total {v} does not match price * qty = {expected}")
        return v
