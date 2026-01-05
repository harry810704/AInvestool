"""
Centralized configuration management for the Investment Dashboard.

This module provides a single source of truth for all application configuration,
including constants, settings, and environment-specific values.
"""

import os
from typing import Dict, List
from dataclasses import dataclass, field


@dataclass
class GoogleDriveConfig:
    """Configuration for Google Drive integration."""
    
    scopes: List[str] = field(default_factory=lambda: [
        "https://www.googleapis.com/auth/drive.file",
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ])
    folder_name: str = "AInvestool"
    portfolio_filename: str = "my_portfolio.xlsx"
    settings_filename: str = "allocation_settings.xlsx"
    accounts_filename: str = "accounts.xlsx"

    # Legacy filenames for migration
    legacy_portfolio_filename: str = "my_portfolio.csv"
    legacy_settings_filename: str = "allocation_settings.json"
    legacy_accounts_filename: str = "accounts.json"


@dataclass
class MarketDataConfig:
    """Configuration for market data services."""
    
    # Cache settings
    exchange_rate_cache_ttl: int = 3600  # 1 hour in seconds
    
    # API settings
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    verify_ssl: bool = False
    
    # Default values
    default_exchange_rate: float = 32.5
    
    # Update settings
    price_update_threshold_days: int = 1
    max_concurrent_updates: int = 10
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0  # seconds


@dataclass
class SecurityConfig:
    """Configuration for security and encryption."""
    
    cookie_name: str = "invest_token_secure"
    cookie_expiry_days: int = 30
    
    # Note: encryption_key should be loaded from secrets, not hardcoded
    @property
    def encryption_key(self) -> str:
        """Get encryption key from Streamlit secrets."""
        import streamlit as st
        return st.secrets.get("security", {}).get("encryption_key", "")


@dataclass
class UIConfig:
    """Configuration for UI components."""
    
    # Page settings
    page_title: str = "個人投資戰情室 Pro (Cloud)"
    page_icon: str = "☁️"
    layout: str = "wide"
    
    # === Asset Categories (Main) ===
    asset_categories: Dict[str, str] = field(default_factory=lambda: {
        "investment": "投資資產",
        "cash": "現金資產",
        "liability": "負債資產"
    })
    
    # === Investment Types ===
    investment_types: List[str] = field(default_factory=lambda: [
        "股票", "虛擬貨幣", "ETF", "債券", "基金", "REITs", "商品", "其他"
    ])
    
    # === Cash Types ===
    cash_types: List[str] = field(default_factory=lambda: [
        "現金", "定存", "活存"
    ])
    
    # === Liability Types ===
    liability_types: List[str] = field(default_factory=lambda: [
        "房貸", "信貸", "車貸", "信用卡", "其他負債"
    ])
    
    # === All Asset Types (for dropdowns) ===
    asset_types: List[str] = field(default_factory=lambda: [
        "股票", "虛擬貨幣", "ETF", "債券", "商品", "現金", "負債", "基金", "REITs", "其他"
    ])
    
    # Account types
    account_types: List[str] = field(default_factory=lambda: [
        "投資帳戶", "現金帳戶", "信用帳戶"
    ])
    
    # Currency options
    currencies: List[str] = field(default_factory=lambda: ["Auto", "USD", "TWD"])
    currency_symbols: Dict[str, str] = field(default_factory=lambda: {"USD": "$", "TWD": "NT$"})
    
    # Display settings
    default_currency: str = "Auto"
    
    # Colors (for charts and UI)
    colors: Dict[str, str] = field(default_factory=lambda: {
        "primary_bar": "#5D69B1",
        "secondary_bar": "#E58606",
        "positive": "green",
        "negative": "red",
        "positive_bg": "#e6fffa",
        "negative_bg": "#fff5f5",
        "positive_text": "#009688",
        "negative_text": "#e53e3e",
        "status_live": "green",
        "status_manual": "#FF4B4B",
    })
    
    # Thresholds
    allocation_tolerance_pct: float = 2.0  # Percentage points


@dataclass
class AllocationDefaults:
    """Default allocation targets."""
    
    targets: Dict[str, float] = field(default_factory=lambda: {
        "美股": 40.0,
        "台股": 40.0,
        "虛擬貨幣": 10.0,
        "稀有金屬": 10.0,
    })


@dataclass
class AppConfig:
    """Main application configuration."""
    
    # Environment
    environment: str = field(default_factory=lambda: os.getenv("APP_ENV", "production"))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    dev_mode: bool = field(default_factory=lambda: os.getenv("DEV_MODE", "false").lower() == "true")
    
    # Sub-configurations
    google_drive: GoogleDriveConfig = field(default_factory=GoogleDriveConfig)
    market_data: MarketDataConfig = field(default_factory=MarketDataConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    allocation: AllocationDefaults = field(default_factory=AllocationDefaults)
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate()
    
    def _validate(self):
        """Validate configuration values."""
        # Validate allocation targets sum to 100%
        total_allocation = sum(self.allocation.targets.values())
        if abs(total_allocation - 100.0) > 0.01:
            import warnings
            warnings.warn(
                f"Default allocation targets sum to {total_allocation}%, not 100%. "
                "This may cause issues with rebalancing calculations."
            )
        
        # Validate positive values
        if self.market_data.price_update_threshold_days < 0:
            raise ValueError("price_update_threshold_days must be positive")
        
        if self.market_data.max_concurrent_updates < 1:
            raise ValueError("max_concurrent_updates must be at least 1")


# Global configuration instance
config = AppConfig()


def get_config() -> AppConfig:
    """
    Get the global configuration instance.
    
    Returns:
        AppConfig: The application configuration
    """
    return config


def reload_config():
    """
    Reload the configuration from environment variables.
    Useful for testing or when environment changes.
    """
    global config
    config = AppConfig()
    return config
