"""
Risk Analysis UI module.

This module provides a dedicated page for analyzing holdings with ATR-based
risk management, stock charts, and cached data for performance.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from modules.risk_management import suggest_sl_tp_for_holding, calculate_atr
from modules.market_service import fetch_historical_data
from modules.logger import get_logger

logger = get_logger(__name__)


@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_cached_historical_data(ticker: str, period: str = '3mo') -> pd.DataFrame:
    """
    Fetch and cache historical data for 1 hour.
    
    Args:
        ticker: Stock ticker symbol
        period: Data period (default: 3mo)
        
    Returns:
        pd.DataFrame: Historical OHLCV data
    """
    logger.info(f"Fetching historical data for {ticker} (will be cached for 1 hour)")
    return fetch_historical_data(ticker, period=period, interval='1d')


@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_cached_atr(ticker: str, period: int = 14) -> Optional[float]:
    """
    Calculate and cache ATR for 1 hour.
    
    Args:
        ticker: Stock ticker symbol
        period: ATR period (default: 14)
        
    Returns:
        float: ATR value or None
    """
    logger.info(f"Calculating ATR for {ticker} (will be cached for 1 hour)")
    return calculate_atr(ticker, period=period)


def create_stock_chart(hist_data: pd.DataFrame, ticker: str, sl_price: Optional[float] = None, 
                       tp_price: Optional[float] = None, avg_cost: Optional[float] = None) -> go.Figure:
    """
    Create an interactive stock chart with SL/TP lines.
    
    Args:
        hist_data: Historical OHLCV data
        ticker: Stock ticker symbol
        sl_price: Stop loss price (optional)
        tp_price: Take profit price (optional)
        avg_cost: Average cost price (optional)
        
    Returns:
        go.Figure: Plotly figure object
    """
    fig = go.Figure()
    
    # Candlestick chart
    fig.add_trace(go.Candlestick(
        x=hist_data.index,
        open=hist_data['Open'],
        high=hist_data['High'],
        low=hist_data['Low'],
        close=hist_data['Close'],
        name=ticker,
        increasing_line_color='#26a69a',
        decreasing_line_color='#ef5350'
    ))
    
    # Add volume bars
    fig.add_trace(go.Bar(
        x=hist_data.index,
        y=hist_data['Volume'],
        name='Volume',
        yaxis='y2',
        marker_color='rgba(128, 128, 128, 0.3)'
    ))
    
    # Add average cost line
    if avg_cost:
        fig.add_hline(
            y=avg_cost,
            line_dash="dash",
            line_color="blue",
            annotation_text=f"平均成本: ${avg_cost:.2f}",
            annotation_position="right"
        )
    
    # Add stop loss line
    if sl_price:
        fig.add_hline(
            y=sl_price,
            line_dash="dot",
            line_color="red",
            annotation_text=f"停損: ${sl_price:.2f}",
            annotation_position="right"
        )
    
    # Add take profit line
    if tp_price:
        fig.add_hline(
            y=tp_price,
            line_dash="dot",
            line_color="green",
            annotation_text=f"停利: ${tp_price:.2f}",
            annotation_position="right"
        )
    
    # Update layout
    fig.update_layout(
        title=f"{ticker} 股價走勢與風控線",
        yaxis_title="價格",
        xaxis_title="日期",
        yaxis2=dict(
            title="成交量",
            overlaying='y',
            side='right',
            showgrid=False
        ),
        hovermode='x unified',
        height=600,
        template='plotly_white',
        xaxis_rangeslider_visible=False,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    return fig


def render_risk_analysis(portfolio: list, c_symbol: str):
    """
    Render the risk analysis page.
    
    Args:
        portfolio: List of portfolio assets
        c_symbol: Currency symbol for display
    """
    st.title("📈 風險分析工具")
    st.caption("選擇持倉進行 ATR 風控分析，查看建議的停損停利線與股價走勢圖")
    
    if not portfolio:
        st.info("目前沒有持倉。請先在「設定與管理」頁面新增資產。")
        return
    
    # Create selection dropdown
    # Create selection dropdown
    # Map keys safely
    ticker_options = []
    for asset in portfolio:
        t = asset.get("symbol") or asset.get("Ticker")
        ty = asset.get("asset_class") or asset.get("Type")
        ticker_options.append(f"{t} ({ty})")
        
    selected_option = st.selectbox(
        "選擇要分析的持倉",
        ticker_options,
        key="risk_analysis_ticker_select"
    )
    
    if not selected_option:
        return
    
    # Get selected asset
    selected_ticker = selected_option.split(" (")[0]
    # Match by symbol/Ticker
    selected_asset = next((a for a in portfolio if (a.get("symbol") or a.get("Ticker")) == selected_ticker), None)
    
    if not selected_asset:
        st.error("找不到選擇的資產")
        return
    
    # Display asset info
    col1, col2, col3, col4 = st.columns(4)
    
    a_ticker = selected_asset.get("symbol") or selected_asset.get("Ticker")
    a_type = selected_asset.get("asset_class") or selected_asset.get("Type")
    a_qty = selected_asset.get("quantity")
    if a_qty is None: a_qty = selected_asset.get("Quantity", 0.0)
    
    a_cost = selected_asset.get("avg_cost")
    if a_cost is None: a_cost = selected_asset.get("Avg_Cost", 0.0)
    
    a_curr = selected_asset.get("currency") or selected_asset.get("Currency", "USD")

    col1.metric("代號", a_ticker)
    col2.metric("類型", a_type)
    col3.metric("持有數量", f"{a_qty:.2f}")
    col4.metric("平均成本", f"{a_curr} {a_cost:.2f}")
    
    st.divider()
    
    # Parameter controls
    st.subheader("⚙️ 風控參數設定")
    col_param1, col_param2, col_param3 = st.columns(3)
    
    with col_param1:
        atr_period = st.slider(
            "ATR 週期",
            min_value=7,
            max_value=30,
            value=14,
            help="計算 ATR 的天數"
        )
    
    with col_param2:
        atr_multiplier = st.slider(
            "ATR 倍數",
            min_value=1.0,
            max_value=5.0,
            value=2.0,
            step=0.5,
            help="用於計算停損距離"
        )
    
    with col_param3:
        r_ratio = st.slider(
            "R-Ratio",
            min_value=1.0,
            max_value=5.0,
            value=2.0,
            step=0.5,
            help="風險回報比"
        )
    
    # Calculate button
    if st.button("🔍 執行分析", type="primary", use_container_width=True):
        with st.spinner(f"正在分析 {selected_ticker}..."):
            # Get current price from manual price or avg cost
            man_price = selected_asset.get("manual_price")
            if man_price is None: man_price = selected_asset.get("Manual_Price", 0.0)
            
            # Using already resolved variables
            current_price = man_price if man_price > 0 else a_cost
            if current_price == 0:
                current_price = a_cost
            
            # Calculate SL/TP
            result = suggest_sl_tp_for_holding(
                ticker=selected_ticker,
                avg_cost=a_cost,
                current_price=current_price,
                atr_multiplier=atr_multiplier,
                r_ratio=r_ratio,
                atr_period=atr_period
            )
            
            if result:
                # Store result in session state
                st.session_state['risk_analysis_result'] = result
                st.session_state['risk_analysis_ticker'] = selected_ticker
                st.session_state['risk_analysis_asset'] = selected_asset
                st.success("✅ 分析完成！")
                st.rerun()
            else:
                st.error("❌ 無法計算 ATR，可能是數據不足或代號錯誤")
    
    # Display results if available
    if 'risk_analysis_result' in st.session_state and \
       st.session_state.get('risk_analysis_ticker') == selected_ticker:
        
        result = st.session_state['risk_analysis_result']
        asset = st.session_state['risk_analysis_asset']
        
        st.divider()
        st.subheader("📊 分析結果")
        
        # Metrics row
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric(
            "ATR 值",
            f"{result['atr_value']:.4f}",
            help="平均真實波動區間"
        )
        col_m2.metric(
            "1R 距離",
            f"{result['one_r_distance']:.2f}",
            help="單位風險距離"
        )
        col_m3.metric(
            "當前風險",
            f"{c_symbol}{result['current_risk']:.2f}",
            help="從成本到停損的距離"
        )
        col_m4.metric(
            "潛在獲利",
            f"{c_symbol}{result['current_reward']:.2f}",
            help="從成本到停利的距離"
        )
        
        st.divider()
        
        # SL/TP display
        col_sl, col_tp = st.columns(2)
        
        with col_sl:
            st.markdown(f"""
            <div style='background-color: #ffebee; padding: 20px; border-radius: 10px; border-left: 5px solid #f44336;'>
                <h3 style='margin: 0; color: #c62828;'>🔴 建議停損價</h3>
                <h1 style='margin: 10px 0; color: #c62828;'>{a_curr} {result['sl_price']:.2f}</h1>
                <p style='margin: 0; color: #666;'>風險: {c_symbol}{result['current_risk']:.2f} / 股</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col_tp:
            st.markdown(f"""
            <div style='background-color: #e8f5e9; padding: 20px; border-radius: 10px; border-left: 5px solid #4caf50;'>
                <h3 style='margin: 0; color: #2e7d32;'>🟢 建議停利價</h3>
                <h1 style='margin: 10px 0; color: #2e7d32;'>{a_curr} {result['tp_price']:.2f}</h1>
                <p style='margin: 0; color: #666;'>目標: {c_symbol}{result['current_reward']:.2f} / 股</p>
            </div>
            """, unsafe_allow_html=True)
        
        st.divider()
        
        # Fetch and display stock chart
        st.subheader("📈 股價走勢圖")
        
        with st.spinner("載入股價圖表..."):
            hist_data = get_cached_historical_data(selected_ticker, period='3mo')
            
            if not hist_data.empty:
                # Show cache info
                st.caption("💾 圖表數據已快取 1 小時，避免重複請求")
                
                # Create and display chart
                fig = create_stock_chart(
                    hist_data,
                    selected_ticker,
                    sl_price=result['sl_price'],
                    tp_price=result['tp_price'],
                    avg_cost=a_cost
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Additional statistics
                with st.expander("📊 詳細統計資訊"):
                    stat_col1, stat_col2, stat_col3 = st.columns(3)
                    
                    
                    current_price = hist_data['Close'].iloc[-1]
                    price_change = current_price - a_cost
                    price_change_pct = (price_change / a_cost * 100) if a_cost > 0 else 0
                    
                    stat_col1.metric(
                        "當前價格",
                        f"{a_curr} {current_price:.2f}",
                        f"{price_change_pct:+.2f}%"
                    )
                    
                    distance_to_sl = current_price - result['sl_price']
                    distance_to_sl_pct = (distance_to_sl / current_price * 100) if current_price > 0 else 0
                    stat_col2.metric(
                        "距離停損",
                        f"{distance_to_sl:.2f}",
                        f"{distance_to_sl_pct:.2f}%"
                    )
                    
                    distance_to_tp = result['tp_price'] - current_price
                    distance_to_tp_pct = (distance_to_tp / current_price * 100) if current_price > 0 else 0
                    stat_col3.metric(
                        "距離停利",
                        f"{distance_to_tp:.2f}",
                        f"{distance_to_tp_pct:.2f}%"
                    )
                    
                    # Position value
                    st.divider()
                    position_value = current_price * a_qty
                    total_risk = result['current_risk'] * a_qty
                    total_reward = result['current_reward'] * a_qty
                    
                    st.markdown(f"""
                    **持倉價值分析:**
                    - 當前市值: {c_symbol}{position_value:,.2f}
                    - 總風險金額: {c_symbol}{total_risk:,.2f}
                    - 總潛在獲利: {c_symbol}{total_reward:,.2f}
                    - 風險回報比: 1:{r_ratio}
                    """)
            else:
                st.warning("無法載入股價圖表數據")
