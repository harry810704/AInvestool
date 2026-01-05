"""
Data models for the Investment Dashboard.

This module defines Pydantic models for type-safe data structures
used throughout the application.
"""

from datetime import datetime
from typing import Optional, Literal, List
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict
import pandas as pd
import uuid


class AccountType(str, Enum):
    """帳戶類型枚舉"""
    BROKERAGE_US = "美股券商"
    BROKERAGE_TW = "台股券商"
    BROKERAGE_HK = "港股券商"
    BANK_CHECKING = "銀行活存"
    BANK_SAVINGS = "銀行定存"
    CREDIT_CARD = "信用卡"
    MORTGAGE = "房貸帳戶"
    AUTO_LOAN = "車貸帳戶"
    PERSONAL_LOAN = "信貸帳戶"
    CRYPTO_EXCHANGE = "加密貨幣交易所"
    RETIREMENT = "退休金帳戶"
    OTHER = "其他"


class Account(BaseModel):
    """
    Enhanced financial account model representing real-world accounts.
    
    Attributes:
        account_id: Unique identifier for the account
        name: Account display name (e.g., "Firstrade 美股帳戶")
        institution: Financial institution name (e.g., "Firstrade", "富邦證券")
        account_type: Account type from AccountType enum
        account_number: Account number (last 4 digits for security)
        base_currency: Base currency for the account
        is_active: Whether the account is currently active
        description: Optional account description
        created_date: Account creation date
    """
    model_config = ConfigDict(validate_assignment=True)
    
    account_id: str = Field(default_factory=lambda: f"acc_{uuid.uuid4().hex[:12]}", description="Unique Account ID")
    name: str = Field(..., description="Account Name")
    institution: str = Field(default="", description="Financial Institution")
    account_type: str = Field(default="其他", description="Account Type")
    account_number: str = Field(default="", description="Account Number (last 4 digits)")
    base_currency: str = Field(default="TWD", description="Base Currency")
    is_active: bool = Field(default=True, description="Is Active")
    description: str = Field(default="", description="Description")
    created_date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"), description="Created Date")
    
    # Legacy field for backward compatibility
    type: Optional[str] = Field(None, description="Legacy type field (deprecated)")
    
    @field_validator('account_type')
    @classmethod
    def validate_account_type(cls, v: str) -> str:
        """Validate account type."""
        # Allow both enum values and legacy types
        valid_types = [e.value for e in AccountType] + ["現金帳戶", "投資帳戶", "信用帳戶"]
        if v not in valid_types:
            import warnings
            warnings.warn(f"Account type '{v}' is not in standard types")
        return v
    
    def to_dict(self) -> dict:
        """Convert to dictionary for Excel serialization."""
        return {
            "account_id": self.account_id,
            "name": self.name,
            "institution": self.institution,
            "account_type": self.account_type,
            "account_number": self.account_number,
            "base_currency": self.base_currency,
            "is_active": self.is_active,
            "description": self.description,
            "created_date": self.created_date
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Account":
        """Create Account from dictionary with backward compatibility."""
        # Handle legacy 'type' field
        account_type = data.get("account_type")
        if not account_type:
            legacy_type = data.get("type", "其他")
            # Map legacy types to new types
            type_mapping = {
                "投資帳戶": "其他",
                "現金帳戶": "銀行活存",
                "信用帳戶": "信用卡"
            }
            account_type = type_mapping.get(legacy_type, "其他")
        
        return cls(
            account_id=str(data.get("account_id") or data.get("id", f"acc_{uuid.uuid4().hex[:12]}")),
            name=str(data.get("name", "")),
            institution=str(data.get("institution", "")),
            account_type=account_type,
            account_number=str(data.get("account_number", "")),
            base_currency=str(data.get("base_currency") or data.get("currency", "TWD")),
            is_active=bool(data.get("is_active", True)),
            description=str(data.get("description", "")),
            created_date=str(data.get("created_date", datetime.now().strftime("%Y-%m-%d")))
        )


class AssetCategory(str, Enum):
    """資產主類別枚舉"""
    INVESTMENT = "investment"    # 投資資產
    CASH = "cash"               # 現金資產
    LIABILITY = "liability"      # 負債資產


class Asset(BaseModel):
    """
    Enhanced asset model with three-tier classification.
    
    Classification:
        - category: Main category (investment/cash/liability)
        - asset_type: Specific type (e.g., "美股", "房貸")
        - sub_type: Optional sub-classification
    """
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )
    
    # === Identity ===
    asset_id: str = Field(default_factory=lambda: f"ast_{uuid.uuid4().hex[:12]}", description="Unique Asset ID")
    account_id: str = Field(..., description="Linked Account ID")
    
    # === Classification ===
    category: str = Field(..., description="Main category (investment/cash/liability)")
    asset_type: str = Field(..., description="Asset/investment type")
    sub_type: Optional[str] = Field(None, description="Sub-classification")
    
    # === Identification ===
    symbol: str = Field(..., description="Ticker/symbol or ID", min_length=1)
    name: str = Field(default="", description="Asset name")
    
    # === Quantity & Cost ===
    quantity: float = Field(..., ge=0, description="Quantity/amount")
    avg_cost: float = Field(default=0.0, ge=0, description="Average cost")
    currency: str = Field(..., description="Currency")
    
    # === Price ===
    current_price: float = Field(default=0.0, ge=0, description="Current price")
    manual_price: float = Field(default=0.0, ge=0, description="Manual price")
    last_update: str = Field(default="N/A", description="Last update")
    
    # === Risk Management ===
    suggested_sl: Optional[float] = Field(None, description="Stop loss")
    suggested_tp: Optional[float] = Field(None, description="Take profit")
    
    # === Liability Specific ===
    loan_plan_id: Optional[str] = Field(None, description="Loan plan ID")
    
    # === Metadata ===
    note: str = Field(default="", description="Notes")
    tags: List[str] = Field(default_factory=list, description="Tags")
    created_date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    modified_date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    
    # === Legacy Fields ===
    type: Optional[str] = Field(None, description="Legacy type (deprecated)")
    ticker: Optional[str] = Field(None, description="Legacy ticker (deprecated)")
    
    @field_validator('symbol')
    @classmethod
    def symbol_validation(cls, v: str, info) -> str:
        """Validate symbol with auto-generation for cash/liabilities."""
        data = info.data
        category = data.get('category', '')
        
        if category in ['cash', 'liability']:
            if not v or v.strip() == "":
                currency = data.get('currency', 'TWD')
                asset_type = data.get('asset_type', '')
                prefix = "CASH" if category == "cash" else asset_type.upper()
                return f"{prefix}-{currency}"
        
        if not v or v.strip() == "":
            raise ValueError("Symbol cannot be empty for investment assets")
        
        return v.upper()
    
    @field_validator('category')
    @classmethod
    def validate_category(cls, v: str) -> str:
        """Validate category."""
        valid = [e.value for e in AssetCategory]
        if v not in valid:
            raise ValueError(f"Category must be one of: {valid}")
        return v
    
    def to_dict(self) -> dict:
        """Convert to dictionary for Excel serialization."""
        return {
            "asset_id": self.asset_id,
            "account_id": self.account_id,
            "category": self.category,
            "asset_type": self.asset_type,
            "sub_type": self.sub_type or "",
            "symbol": self.symbol,
            "name": self.name,
            "quantity": self.quantity,
            "avg_cost": self.avg_cost,
            "currency": self.currency,
            "current_price": self.current_price,
            "manual_price": self.manual_price,
            "last_update": self.last_update,
            "suggested_sl": self.suggested_sl if self.suggested_sl else "",
            "suggested_tp": self.suggested_tp if self.suggested_tp else "",
            "loan_plan_id": self.loan_plan_id or "",
            "note": self.note,
            "tags": ",".join(self.tags) if self.tags else "",
            "created_date": self.created_date,
            "modified_date": self.modified_date
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Asset":
        """Create Asset with migration logic for legacy data."""
        
        # Migration logic
        category = data.get("category")
        asset_type = data.get("asset_type") or data.get("Type") or data.get("asset_class")
        
        if not category and asset_type:
            # Migrate from old format
            category, migrated_type, sub_type = cls._migrate_legacy_type(asset_type)
            if not data.get("asset_type"):
                asset_type = migrated_type
        
        # Handle symbol/ticker
        symbol = data.get("symbol") or data.get("Ticker") or data.get("ticker", "")
        
        # Parse optional floats
        def parse_opt_float(k1: str, k2: str = "") -> Optional[float]:
            val = data.get(k1) or (data.get(k2) if k2 else None)
            if val is None or val == "" or val == "N/A":
                return None
            try:
                return float(val)
            except:
                return None
        
        # Parse tags - handle both string and non-string values
        tags_str = data.get("tags", "")
        if tags_str and not isinstance(tags_str, str):
            # Handle NaN or numeric values from Excel
            try:
                tags_str = str(tags_str) if str(tags_str) != "nan" else ""
            except:
                tags_str = ""
        tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
        
        # Helper to safely get string value, converting NaN to None or empty string
        def safe_str(val, allow_none=False):
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return None if allow_none else ""
            return str(val) if val else ""
        
        return cls(
            asset_id=str(data.get("asset_id") or f"ast_{uuid.uuid4().hex[:12]}"),
            account_id=str(data.get("account_id") or data.get("Account_ID", "default_main")),
            category=category or "investment",
            asset_type=str(asset_type or "其他"),
            sub_type=safe_str(data.get("sub_type"), allow_none=True),
            symbol=symbol,
            name=str(data.get("name", "")),
            quantity=float(data.get("quantity") or data.get("Quantity", 0)),
            avg_cost=float(data.get("avg_cost") or data.get("Avg_Cost", 0)),
            currency=data.get("currency") or data.get("Currency", "USD"),
            current_price=float(data.get("current_price", 0)),
            manual_price=float(data.get("manual_price") or data.get("Manual_Price", 0)),
            last_update=safe_str(data.get("last_update") or data.get("Last_Update", "N/A")),
            suggested_sl=parse_opt_float("suggested_sl", "Suggested_SL"),
            suggested_tp=parse_opt_float("suggested_tp", "Suggested_TP"),
            loan_plan_id=safe_str(data.get("loan_plan_id"), allow_none=True),
            note=str(data.get("note", "")),
            tags=tags,
            created_date=str(data.get("created_date", datetime.now().strftime("%Y-%m-%d"))),
            modified_date=str(data.get("modified_date", datetime.now().strftime("%Y-%m-%d")))
        )
    
    @staticmethod
    def _migrate_legacy_type(old_type: str) -> tuple[str, str, Optional[str]]:
        """Migrate legacy type to (category, asset_type, sub_type)."""
        investment_types = ["美股", "台股", "港股", "虛擬貨幣", "稀有金屬", "ETF", "債券", "基金", "REITs"]
        if old_type in investment_types:
            return ("investment", old_type, None)
        if old_type == "現金":
            return ("cash", "現金", None)
        if old_type == "負債":
            return ("liability", "其他負債", None)
        return ("investment", old_type, None)



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


class HistoryRecord(BaseModel):
    """
    Represents a historical snapshot of the portfolio.
    
    Attributes:
        date: Snapshot date (YYYY-MM-DD)
        total_net_worth_twd: Total net worth in TWD
        total_net_worth_usd: Total net worth in USD
        us_stock_val: Value of US stocks
        tw_stock_val: Value of TW stocks
        cash_val: Value of Cash
        crypto_val: Value of Crypto
        loan_val: Value of Loans/Liabilities
    """
    
    model_config = ConfigDict(validate_assignment=True)
    
    date: str
    total_net_worth_twd: float
    total_net_worth_usd: float
    us_stock_val: float = 0.0
    tw_stock_val: float = 0.0
    cash_val: float = 0.0
    crypto_val: float = 0.0
    loan_val: float = 0.0
    # Extendable for other classes if needed, maybe use extra="allow" logic or map explicitly
    
    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "total_net_worth_twd": self.total_net_worth_twd,
            "total_net_worth_usd": self.total_net_worth_usd,
            "us_stock_val": self.us_stock_val,
            "tw_stock_val": self.tw_stock_val,
            "cash_val": self.cash_val,
            "crypto_val": self.crypto_val,
            "loan_val": self.loan_val,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "HistoryRecord":
        # Handle excel timestamp if it comes as datetime object
        d = data.get("date")
        if hasattr(d, "strftime"):
            d = d.strftime("%Y-%m-%d")
        elif not d or pd.isna(d):
            d = datetime.now().strftime("%Y-%m-%d")
            
        return cls(
            date=str(d),
            total_net_worth_twd=float(data.get("total_net_worth_twd", 0)),
            total_net_worth_usd=float(data.get("total_net_worth_usd", 0)),
            us_stock_val=float(data.get("us_stock_val", 0)),
            tw_stock_val=float(data.get("tw_stock_val", 0)),
            cash_val=float(data.get("cash_val", 0)),
            crypto_val=float(data.get("crypto_val", 0)),
            loan_val=float(data.get("loan_val", 0)),
        )


class LoanScheduleItem(BaseModel):
    """
    Single item in a loan amortization schedule.
    """
    payment_number: int
    date: str
    payment_amount: float
    principal_paid: float
    interest_paid: float
    remaining_balance: float
    
    def to_dict(self) -> dict:
        return {
            "payment_number": self.payment_number,
            "date": self.date,
            "payment_amount": self.payment_amount,
            "principal_paid": self.principal_paid,
            "interest_paid": self.interest_paid,
            "remaining_balance": self.remaining_balance
        }


class LoanPlan(BaseModel):
    """
    Represents a loan repayment plan linked to a Liability Asset.
    """
    asset_id: str = Field(..., description="ID of the Liability Asset")
    total_amount: float = Field(..., gt=0, description="Total Loan Amount")
    annual_rate: float = Field(..., ge=0, description="Annual Interest Rate (%)")
    period_months: int = Field(..., gt=0, description="Loan Duration in Months")
    start_date: str = Field(..., description="Loan Start Date (YYYY-MM-DD)")
    schedule: list[LoanScheduleItem] = Field(default_factory=list, description="Amortization Schedule")
    
    extra_fees: float = Field(default=0.0, ge=0, description="One-time fees or setup costs")
    
    def to_dict(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "total_amount": self.total_amount,
            "annual_rate": self.annual_rate,
            "period_months": self.period_months,
            "start_date": self.start_date,
            "extra_fees": self.extra_fees,
            # Schedule is usually derived or stored in a separate table structure for Excel flattened view
            # But for object completeness we keep it here.
            # When saving to Excel, we might just save the Plan params or the full schedule.
        }
