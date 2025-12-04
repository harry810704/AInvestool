"""
Risk management module for SL/TP calculations.

This module provides ATR-based stop loss and take profit calculations
using the Average True Range (ATR) indicator and R-Ratio (risk-reward ratio).
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from modules.logger import get_logger
from modules.market_service import fetch_historical_data

logger = get_logger(__name__)


def calculate_atr(ticker: str, period: int = 14) -> Optional[float]:
    """
    Calculate Average True Range (ATR) for a ticker.
    
    ATR measures market volatility by decomposing the entire range of an asset
    price for that period. It's calculated as the average of true ranges over
    a specified period.
    
    Args:
        ticker: Stock ticker symbol
        period: Number of periods for ATR calculation (default: 14)
        
    Returns:
        float: ATR value, or None if calculation fails
    """
    try:
        # Fetch historical data (need at least period+1 days)
        hist = fetch_historical_data(ticker, period='3mo', interval='1d')
        
        if hist.empty or len(hist) < period + 1:
            logger.warning(f"Insufficient data for ATR calculation: {ticker}")
            return None
        
        # Calculate True Range (TR)
        # TR = max(high - low, abs(high - prev_close), abs(low - prev_close))
        high = hist['High']
        low = hist['Low']
        close = hist['Close']
        prev_close = close.shift(1)
        
        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Calculate ATR as simple moving average of TR
        atr = true_range.rolling(window=period).mean().iloc[-1]
        
        logger.debug(f"Calculated ATR for {ticker}: {atr:.4f}")
        return float(atr)
        
    except Exception as e:
        logger.error(f"Failed to calculate ATR for {ticker}: {e}")
        return None


def suggest_sl_tp_for_entry(
    entry_price: float,
    atr_value: float,
    max_loss_amount: float,
    atr_multiplier: float = 2.0,
    r_ratio: float = 2.0
) -> Dict[str, float]:
    """
    Calculate SL/TP suggestions for a new entry position.
    
    This function helps determine position sizing based on maximum acceptable loss
    and calculates stop loss and take profit levels using ATR.
    
    Args:
        entry_price: Planned entry price per share
        atr_value: Current ATR value for the asset
        max_loss_amount: Maximum acceptable loss in dollars
        atr_multiplier: Multiplier for ATR to set stop distance (default: 2.0)
        r_ratio: Risk-reward ratio (default: 2.0, meaning 2:1 reward:risk)
        
    Returns:
        dict: Dictionary containing:
            - sl_price: Suggested stop loss price
            - tp_price: Suggested take profit price
            - max_qty: Maximum quantity to buy based on max loss
            - one_r_distance: The 1R distance in dollars
            - risk_amount: Total risk amount (should equal max_loss_amount)
            - reward_amount: Potential reward amount
    """
    # Calculate 1R distance (the amount risked per share)
    one_r_distance = atr_value * atr_multiplier
    
    # Calculate SL and TP prices
    sl_price = entry_price - one_r_distance
    tp_price = entry_price + (one_r_distance * r_ratio)
    
    # Calculate maximum quantity based on max loss
    # max_loss = quantity * one_r_distance
    # Therefore: quantity = max_loss / one_r_distance
    max_qty = max_loss_amount / one_r_distance if one_r_distance > 0 else 0
    
    # Calculate actual risk and reward amounts
    risk_amount = max_qty * one_r_distance
    reward_amount = max_qty * (one_r_distance * r_ratio)
    
    result = {
        'sl_price': round(sl_price, 2),
        'tp_price': round(tp_price, 2),
        'max_qty': round(max_qty, 2),
        'one_r_distance': round(one_r_distance, 4),
        'risk_amount': round(risk_amount, 2),
        'reward_amount': round(reward_amount, 2),
    }
    
    logger.debug(f"Entry SL/TP calculated: {result}")
    return result


def suggest_sl_tp_for_holding(
    ticker: str,
    avg_cost: float,
    current_price: float,
    atr_multiplier: float = 2.0,
    r_ratio: float = 2.0,
    atr_period: int = 14
) -> Optional[Dict[str, float]]:
    """
    Calculate SL/TP suggestions for an existing holding.
    
    This function calculates stop loss and take profit levels for positions
    you already own, based on your average cost and current ATR.
    
    Args:
        ticker: Stock ticker symbol
        avg_cost: Average cost per share
        current_price: Current market price
        atr_multiplier: Multiplier for ATR to set stop distance (default: 2.0)
        r_ratio: Risk-reward ratio (default: 2.0)
        atr_period: Period for ATR calculation (default: 14)
        
    Returns:
        dict: Dictionary containing:
            - sl_price: Suggested stop loss price
            - tp_price: Suggested take profit price
            - atr_value: Current ATR value
            - one_r_distance: The 1R distance in dollars
            - current_risk: Current risk from avg_cost to SL
            - current_reward: Potential reward from avg_cost to TP
            - unrealized_pl_pct: Current unrealized P/L percentage
        Returns None if ATR calculation fails
    """
    # Calculate ATR
    atr_value = calculate_atr(ticker, period=atr_period)
    
    if atr_value is None:
        logger.warning(f"Cannot calculate SL/TP for {ticker}: ATR unavailable")
        return None
    
    # Calculate 1R distance
    one_r_distance = atr_value * atr_multiplier
    
    # Calculate SL and TP based on average cost
    sl_price = avg_cost - one_r_distance
    tp_price = avg_cost + (one_r_distance * r_ratio)
    
    # Calculate risk and reward from current position
    current_risk = avg_cost - sl_price
    current_reward = tp_price - avg_cost
    
    # Calculate unrealized P/L percentage
    unrealized_pl_pct = ((current_price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0
    
    result = {
        'sl_price': round(sl_price, 2),
        'tp_price': round(tp_price, 2),
        'atr_value': round(atr_value, 4),
        'one_r_distance': round(one_r_distance, 4),
        'current_risk': round(current_risk, 2),
        'current_reward': round(current_reward, 2),
        'unrealized_pl_pct': round(unrealized_pl_pct, 2),
    }
    
    logger.debug(f"Holding SL/TP calculated for {ticker}: {result}")
    return result
