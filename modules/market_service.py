"""
Market data service module.

This module handles fetching market data from Yahoo Finance,
including exchange rates, stock prices, and portfolio updates.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed

from modules.logger import get_logger
from modules.exceptions import MarketDataError
from models import PriceUpdate, MarketData
from config import get_config

logger = get_logger(__name__)
config = get_config()

# Note: yfinance now uses curl_cffi internally, no need for custom session


@st.cache_data(ttl=config.market_data.exchange_rate_cache_ttl)
def get_exchange_rate() -> float:
    """
    Get USD to TWD exchange rate.
    
    Returns:
        float: Current exchange rate, or default if fetch fails
    """
    try:
        ticker = yf.Ticker("TWD=X")
        hist = ticker.history(period="1d")
        if not hist.empty:
            rate = hist["Close"].iloc[-1]
            logger.debug(f"Fetched exchange rate: 1 USD = {rate:.2f} TWD")
            return rate
        logger.warning("No exchange rate data, using default")
        return config.market_data.default_exchange_rate
    except Exception as e:
        logger.error(f"Failed to fetch exchange rate: {e}")
        return config.market_data.default_exchange_rate


def search_yahoo_ticker(query: str) -> List[str]:
    """
    Search for ticker symbols on Yahoo Finance.
    
    Args:
        query: Search query string
        
    Returns:
        List[str]: List of formatted search results
    """
    if not query:
        return []
    
    try:
        import requests
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}&lang=en-US&region=US&quotesCount=10&newsCount=0"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = []
        if "quotes" in data:
            for item in data["quotes"]:
                if "symbol" in item:
                    symbol = item["symbol"]
                    name = item.get("shortname", item.get("longname", "Unknown"))
                    exch = item.get("exchDisp", "Unknown")
                    display_str = f"{symbol} | {name} ({exch})"
                    results.append(display_str)
        
        logger.debug(f"Search for '{query}' returned {len(results)} results")
        return results
    except Exception as e:
        logger.error(f"Ticker search failed for '{query}': {e}")
        return []


def fetch_historical_data(ticker: str, period: str = '1mo', interval: str = '1d') -> pd.DataFrame:
    """
    Fetch historical OHLCV data for a ticker.
    
    Args:
        ticker: Stock ticker symbol
        period: Data period (e.g., '1mo', '3mo', '6mo', '1y')
        interval: Data interval (e.g., '1d', '1h', '5m')
        
    Returns:
        pd.DataFrame: DataFrame with columns [Open, High, Low, Close, Volume]
                     Returns empty DataFrame if fetch fails
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period, interval=interval)
        
        if not hist.empty:
            logger.debug(f"Fetched {len(hist)} rows of historical data for {ticker}")
            return hist
        
        logger.warning(f"No historical data available for {ticker}")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Failed to fetch historical data for {ticker}: {e}")
        return pd.DataFrame()


def fetch_single_price(ticker: str) -> Tuple[bool, float, Optional[str]]:
    """
    Fetch current price for a single ticker.
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        Tuple[bool, float, Optional[str]]: (success, price, error_message)
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        
        if not hist.empty:
            price = hist["Close"].iloc[-1]
            logger.debug(f"Fetched price for {ticker}: {price}")
            return True, price, None
        
        # Try fast_info as fallback
        try:
            price = stock.fast_info["last_price"]
            if price and price > 0:
                logger.debug(f"Fetched price (fast_info) for {ticker}: {price}")
                return True, price, None
        except Exception:
            pass
        
        logger.warning(f"No price data available for {ticker}")
        return False, 0.0, "No Data"
    except Exception as e:
        logger.error(f"Failed to fetch price for {ticker}: {e}")
        return False, 0.0, str(e)


def check_is_outdated(last_update_str: str) -> bool:
    """
    Check if price data is outdated.
    
    Args:
        last_update_str: Last update timestamp string
        
    Returns:
        bool: True if data is outdated
    """
    if not last_update_str or last_update_str == "N/A":
        return True
    
    try:
        last_update_dt = datetime.strptime(last_update_str, "%Y-%m-%d %H:%M")
        threshold = timedelta(days=config.market_data.price_update_threshold_days)
        is_outdated = datetime.now() - last_update_dt > threshold
        return is_outdated
    except Exception as e:
        logger.warning(f"Failed to parse update time '{last_update_str}': {e}")
        return True


def auto_update_portfolio(portfolio: List[dict]) -> Tuple[int, int, List[dict]]:
    """
    Automatically update outdated asset prices in portfolio.
    
    Uses parallel fetching for improved performance.
    
    Args:
        portfolio: List of asset dictionaries
        
    Returns:
        Tuple[int, int, List[dict]]: (success_count, fail_count, updated_portfolio)
    """
    # Find outdated items
    outdated_items = []
    for i, item in enumerate(portfolio):
        # Skip Cash and Liability for auto-updates
        if item.get("Type") in ["現金", "負債"]:
            continue
            
        if "Last_Update" not in item:
            item["Last_Update"] = "N/A"
        
        if check_is_outdated(item["Last_Update"]):
            outdated_items.append((i, item))
            
    if not outdated_items:
        logger.info("No outdated assets to update")
        return 0, 0, portfolio
    
    logger.info(f"Updating {len(outdated_items)} outdated assets")
    
    success_count = 0
    fail_count = 0
    
    # Parallel fetch with ThreadPoolExecutor
    max_workers = config.market_data.max_concurrent_updates
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit tasks
        future_to_index = {
            executor.submit(fetch_single_price, item["Ticker"]): index
            for index, item in outdated_items
        }
        
        # Collect results
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                ok, price, err = future.result()
                if ok:
                    portfolio[index]["Manual_Price"] = price
                    portfolio[index]["Last_Update"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    success_count += 1
                    logger.debug(f"Updated {portfolio[index]['Ticker']}: {price}")
                else:
                    fail_count += 1
                    logger.warning(f"Failed to update {portfolio[index]['Ticker']}: {err}")
            except Exception as e:
                fail_count += 1
                logger.error(f"Exception updating asset at index {index}: {e}")
    
    logger.info(f"Update complete: {success_count} success, {fail_count} failed")
    return success_count, fail_count, portfolio


def get_market_data(
    portfolio: List[dict],
    target_currency: str,
    usd_twd_rate: float
) -> pd.DataFrame:
    """
    Get market data for all assets in portfolio.
    
    Args:
        portfolio: List of asset dictionaries
        target_currency: Target currency for display (USD or TWD)
        usd_twd_rate: Current USD to TWD exchange rate
        
    Returns:
        pd.DataFrame: DataFrame with market data for all assets
    """
    if not portfolio:
        logger.debug("Empty portfolio, returning empty DataFrame")
        return pd.DataFrame()
    
    logger.info(f"Fetching market data for {len(portfolio)} assets")
    data_list = []
    
    # Determine Base Currency for aggregation (default to TWD if Auto)
    base_currency = "TWD" if target_currency == "Auto" else target_currency
    
    for item in portfolio:
        ticker = item["Ticker"]
        asset_type = item["Type"] # Added access to Type
        asset_currency = item.get("Currency", "USD")
        manual_price = item.get("Manual_Price", 0.0)
        last_update = item.get("Last_Update", "N/A")
        
        current_price = 0.0
        daily_change_pct = 0.0
        history_data = pd.Series()
        status = "⚠️ 待更新"
        
        # Skip Yahoo fetch for Cash/Liability
        if asset_type in ["現金", "負債"]:
             # For Cash/Liability, Price is usually 1 (face value) or Manual Price
             # If Manual Price is set, use it. Otherwise default to 1.
             if manual_price > 0:
                 current_price = manual_price
             else:
                 current_price = 1.0 # Default face value
                 
             status = "✅ 手動"
             # Dummy history
             dates = pd.date_range(end=datetime.today(), periods=30)
             history_data = pd.Series([current_price] * 30, index=dates)
             
        else:
            # Existing logic for standard assets
            # Check if we have fresh cached data (within 24 hours)
            is_outdated = check_is_outdated(last_update)
            
            if not is_outdated and manual_price > 0:
                # Use cached price
                current_price = manual_price
                status = "💾 快取 (24h內)"
                logger.debug(f"Using cached price for {ticker}: {manual_price}")
                
                dates = pd.date_range(end=datetime.today(), periods=30)
                history_data = pd.Series([current_price] * 30, index=dates)
            else:
                try:
                    stock = yf.Ticker(ticker)
                    hist = stock.history(period="1mo")
                    
                    if not hist.empty:
                        raw_price = hist["Close"].iloc[-1]
                        raw_prev = hist["Close"].iloc[-2] if len(hist) > 1 else raw_price
                        daily_change_pct = (raw_price - raw_prev) / raw_prev if raw_prev > 0 else 0
                        history_data = hist["Close"]
                        current_price = raw_price
                        status = "✅ 即時"
                    else:
                        raise Exception("No Data")
                except Exception as e:
                    logger.debug(f"Live data unavailable for {ticker}: {e}")
                    status = "⚠️ 手動/舊資料"
                    
                    if manual_price > 0:
                        current_price = manual_price
                    else:
                        current_price = item["Avg_Cost"]
                        status = "⚠️ 僅顯示成本"
                    
                    dates = pd.date_range(end=datetime.today(), periods=30)
                    history_data = pd.Series([current_price] * 30, index=dates)
        
        # --- Currency Conversion Logic ---
        # 1. Calculate Multiplier to Base Currency (for Aggregation)
        rate_multiplier = 1.0
        if base_currency == "TWD" and asset_currency == "USD":
            rate_multiplier = usd_twd_rate
        elif base_currency == "USD" and asset_currency == "TWD":
            rate_multiplier = 1.0 / usd_twd_rate if usd_twd_rate > 0 else 1.0
        
        # Standard Metrics in Base Currency (e.g. TWD)
        base_price = current_price * rate_multiplier
        base_avg_cost = item["Avg_Cost"] * rate_multiplier
        
        market_value_base = base_price * item["Quantity"]
        total_cost_base = base_avg_cost * item["Quantity"]
        
        # Net Value logic: Liabilities are negative contribution to Net Worth
        net_value_base = -market_value_base if asset_type == "負債" else market_value_base
        
        unrealized_pl_base = market_value_base - total_cost_base
        # For liability: PL is Debt Decrease? Or Debt Increase is Loss?
        # Usually: Cost (Principal) - Current (Balance). If Balance > Cost, Loss.
        # PL = Cost - MarketValue? 
        # If I borrowed 100 (Cost), now owe 110 (MarketValue), PL is -10.
        # So PL = Cost - MarketValue logic works for Liability?
        # Let's check: 100 (Cost) - 110 (Val) = -10. Correct.
        # For Asset: 110 (Val) - 100 (Cost) = 10.
        if asset_type == "負債":
             unrealized_pl_base = total_cost_base - market_value_base
        
        roi = (unrealized_pl_base / total_cost_base) * 100 if total_cost_base > 0 else 0
        
        # 2. Calculate Display Values
        # If Auto, use Native. Else use Base.
        display_curr_code = asset_currency if target_currency == "Auto" else base_currency
        
        if target_currency == "Auto":
            # Display is Native
            display_price = current_price
            display_cost_basis = item["Avg_Cost"]
            display_market_value = current_price * item["Quantity"]
            display_total_cost = display_cost_basis * item["Quantity"]
            
            if asset_type == "負債":
                display_pl = display_total_cost - display_market_value
            else:
                display_pl = display_market_value - display_total_cost
        else:
            # Display is Base (Converted)
            display_price = base_price
            display_cost_basis = base_avg_cost
            display_market_value = market_value_base
            display_total_cost = total_cost_base
            display_pl = unrealized_pl_base

        
        data_list.append({
            "Type": asset_type,
            "Ticker": ticker,
            "Quantity": item["Quantity"],
            
            # Base Columns (Used for Totals/Sorting)
            "Current_Price": base_price,
            "Market_Value": market_value_base, 
            "Net_Value": net_value_base, # New column for Net Worth
            "Total_Cost": total_cost_base,
            "Unrealized_PL": unrealized_pl_base,
            
            # Display Columns (Used for UI showing)
            "Display_Price": display_price,
            "Display_Cost_Basis": display_cost_basis,
            "Display_Market_Value": display_market_value,
            "Display_Total_Cost": display_total_cost,
            "Display_PL": display_pl,
            "Display_Currency": display_curr_code,
            
            "ROI (%)": roi,
            "Daily_Change (%)": daily_change_pct * 100,
            "History": history_data,
            "Status": status,
            "Avg_Cost": base_avg_cost, # Keep for backward compat, but use Display_Cost_Basis in UI
            "Currency": asset_currency,
            "Last_Update": item.get("Last_Update", "N/A"),
            "Account_ID": item.get("Account_ID", "default_main"),
        })
    
    logger.info(f"Market data fetched for {len(data_list)} assets")
    return pd.DataFrame(data_list)
