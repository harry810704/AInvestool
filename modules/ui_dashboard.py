"""
Dashboard UI components.

This module provides UI rendering functions for the investment dashboard,
including KPIs, rebalancing analysis, and portfolio details.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import html
from typing import Optional

from datetime import datetime
from config import get_config
from modules.data_loader import save_snapshot
from modules.logger import get_logger

config = get_config()
logger = get_logger(__name__)

def render_hud_kpi(total_val: float, assets_val: float, liabilities_val: float, g_pl: float, g_roi: float, c_symbol: str):
    """Render the Heads-Up Display (HUD) with Tech styling."""

    # Tech Card HTML Template
    def tech_card_html(label, value, sub_value, color_class):
        safe_label = html.escape(str(label))
        safe_value = html.escape(str(value))
        safe_sub_value = html.escape(str(sub_value))
        return f"""
        <div class="tech-card" style="text-align: center;">
            <div style="color: #94A3B8; font-size: 0.8rem; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 8px;">{safe_label}</div>
            <div class="{color_class}" style="font-size: 1.8rem; font-weight: 700; font-family: 'SF Mono', monospace;">{safe_value}</div>
            <div style="color: #64748B; font-size: 0.75rem; margin-top: 8px;">{safe_sub_value}</div>
        </div>
        """

    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.markdown(tech_card_html(
            "Net Worth",
            f"{c_symbol}{total_val:,.0f}",
            "總資產淨值",
            "neon-text-blue"
        ), unsafe_allow_html=True)

    with c2:
        pl_color = "neon-text-blue" if g_pl >= 0 else "neon-text-pink"
        pl_sign = "+" if g_pl >= 0 else ""
        st.markdown(tech_card_html(
            "Total P/L",
            f"{pl_sign}{c_symbol}{g_pl:,.0f}",
            f"未實現損益",
            pl_color
        ), unsafe_allow_html=True)

    with c3:
        roi_color = "neon-text-blue" if g_roi >= 0 else "neon-text-pink"
        roi_sign = "+" if g_roi >= 0 else ""
        st.markdown(tech_card_html(
            "Lifetime ROI",
            f"{roi_sign}{g_roi:.2f}%",
            "總投資報酬率",
            roi_color
        ), unsafe_allow_html=True)

    with c4:
        # Debt Ratio
        ratio = (abs(liabilities_val) / assets_val * 100) if assets_val > 0 else 0
        ratio_color = "neon-text-blue" if ratio < 30 else ("neon-text-pink" if ratio > 60 else "text-warning")

        st.markdown(tech_card_html(
            "Debt Ratio",
            f"{ratio:.1f}%",
            f"負債: {c_symbol}{abs(liabilities_val):,.0f}",
            ratio_color
        ), unsafe_allow_html=True)

def render_sunburst_allocation(df_all: pd.DataFrame, total_val: float):
    """Render Plotly Sunburst chart for allocation."""
    if df_all.empty:
        return

    # Filter out 0 value assets to clean up chart
    df_chart = df_all[df_all['Market_Value'] > 0].copy()
    
    # If Type and Ticker are the same, it messes up Sunburst sometimes, but usually fine
    # Hierarchy: Type -> Ticker
    
    fig = px.sunburst(
        df_chart,
        path=['Type', 'Ticker'],
        values='Market_Value',
        color='Type',
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    
    fig.update_layout(
        margin=dict(t=0, l=0, r=0, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#FAFAFA'),
        height=350
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_health_monitor(assets_val: float, liabilities_val: float, c_symbol: str):
    """Render Debt Health Gauge."""
    abs_liability = abs(liabilities_val)
    total_exposure = assets_val + abs_liability # Just a base for gauge max
    
    if assets_val == 0:
        ratio = 100
    else:
        ratio = (abs_liability / assets_val) * 100
        
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = ratio,
        title = {'text': "負債比率 %", 'font': {'size': 14, 'color': '#94A3B8'}},
        number = {'suffix': "%", 'font': {'color': "#FAFAFA"}},
        gauge = {
            'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "#334155"},
            'bar': {'color': "#FF0055" if ratio > 50 else "#00B4D8"},
            'bgcolor': "rgba(30, 33, 43, 0.5)",
            'borderwidth': 0,
            'steps': [
                {'range': [0, 30], 'color': 'rgba(0, 255, 0, 0.1)'},
                {'range': [30, 60], 'color': 'rgba(255, 255, 0, 0.1)'},
                {'range': [60, 100], 'color': 'rgba(255, 0, 0, 0.1)'}],
        }
    ))
    
    fig.update_layout(
        margin=dict(t=30, b=10, l=30, r=30),
        paper_bgcolor='rgba(0,0,0,0)',
        font={'color': "#FAFAFA"},
        height=200
    )

    st.plotly_chart(fig, use_container_width=True)

    # Text insight
    if ratio == 0:
        st.caption("✨ 財務狀況極佳 (無負債)")
    elif ratio < 30:
        st.caption("✅ 財務狀況健康")
    elif ratio < 60:
        st.caption("⚠️ 注意槓桿風險")
    else:
        st.caption("🚨 負債比例過高")

def render_mini_trend(history: list, c_symbol: str):
    """Render a mini sparkline-style trend."""
    if not history:
        st.info("尚無歷史數據")
        return

    df = pd.DataFrame(history)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    
    y_col = "total_net_worth_usd" if "$" in c_symbol and "NT" not in c_symbol else "total_net_worth_twd"

    fig = px.area(
        df, x='date', y=y_col,
        line_shape='spline'
    )

    fig.update_traces(
        line=dict(color='#00B4D8', width=2),
        fillcolor='rgba(0, 180, 216, 0.1)'
    )

    fig.update_layout(
        xaxis=dict(showgrid=False, showticklabels=False, title=None),
        yaxis=dict(showgrid=False, showticklabels=False, title=None),
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=150,
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_account_cards(df_all: pd.DataFrame, c_symbol: str):
    """Render account breakdown as glass cards."""
    # Get accounts from session state
    accounts = st.session_state.get("accounts", [])
    if not accounts:
        return

    # Map account IDs to names
    account_map = {
        acc.get("account_id") or acc.get("id"): acc.get("name")
        for acc in accounts
    }
    
    # Logic to group by account (same as before)
    portfolio = st.session_state.get("portfolio", [])
    ticker_to_account = {}
    for asset in portfolio:
        ticker = asset.get("symbol") or asset.get("Ticker")
        acc_id = asset.get("account_id") or asset.get("Account_ID", "default_main")
        ticker_to_account[ticker] = acc_id
    
    if "Account_ID" not in df_all.columns:
        df_all["Account_ID"] = df_all["Ticker"].map(ticker_to_account).fillna("default_main")
    
    account_totals = df_all.groupby("Account_ID").agg({
        "Net_Value": "sum",
        "Unrealized_PL": "sum"
    }).reset_index()
    
    st.markdown("### 🏦 Accounts")
    
    cols = st.columns(3)
    for idx, row in account_totals.iterrows():
        acc_name = account_map.get(row['Account_ID'], "Unknown")
        val = row['Net_Value']
        pl = row['Unrealized_PL']

        col_idx = idx % 3
        with cols[col_idx]:
            # Mini card
            safe_acc_name = html.escape(str(acc_name))
            st.markdown(f"""
            <div class="tech-card" style="padding: 15px;">
                <div style="font-size: 0.9rem; color: #94A3B8;">{safe_acc_name}</div>
                <div style="font-size: 1.2rem; font-weight: bold; color: #FAFAFA;">{c_symbol}{val:,.0f}</div>
                <div style="font-size: 0.8rem; color: {'#00B4D8' if pl>=0 else '#FF0055'};">
                    {'+' if pl>=0 else ''}{c_symbol}{pl:,.0f}
                </div>
            </div>
            """, unsafe_allow_html=True)

def render_dashboard(df_all: pd.DataFrame, c_symbol: str, total_val: float, exchange_rate: float = 32.5) -> None:
    """
    Render the main dashboard view (Redesigned).
    """
    if df_all.empty:
        st.info("Welcome! Please add assets in the Management tab.")
        return

    # Snapshot Button (Top Right)
    c_head, c_btn = st.columns([0.85, 0.15])
    with c_head:
        st.caption(f"Last Update: {datetime.now().strftime('%H:%M')}")
    with c_btn:
        if st.button("📸 Snapshot", use_container_width=True):
             # Logic duplicate from original (simplified here for brevity)
            breakdown = df_all.groupby('Type')['Market_Value'].sum().to_dict()
            is_usd = "$" in c_symbol and "NT" not in c_symbol
            if is_usd:
                tot_usd = total_val
                tot_twd = total_val * exchange_rate
            else:
                tot_twd = total_val
                tot_usd = total_val / exchange_rate if exchange_rate > 0 else 0

            breakdown_twd = {}
            for k, v in breakdown.items():
                if is_usd: breakdown_twd[k] = v * exchange_rate
                else: breakdown_twd[k] = v
                    
            save_snapshot(tot_twd, tot_usd, breakdown_twd)
            st.toast("Snapshot saved to history!", icon="📸")

    # 1. HUD Section
    # Calculate aggregates
    if "Category" in df_all.columns:
        assets_mask = df_all['Category'] != 'liability'
        liabilities_mask = df_all['Category'] == 'liability'
        assets_val = df_all[assets_mask]['Market_Value'].sum()
        liabilities_val = df_all[liabilities_mask]['Market_Value'].sum()
        g_cost = df_all[assets_mask]['Total_Cost'].sum()
    else:
        # Fallback
        liabilities_mask = pd.Series([False] * len(df_all), index=df_all.index)
        if 'Type' in df_all.columns: liabilities_mask |= (df_all['Type'] == '負債')
        if 'asset_type' in df_all.columns: liabilities_mask |= (df_all['asset_type'] == '負債')
        if 'asset_class' in df_all.columns: liabilities_mask |= (df_all['asset_class'] == '負債')
        
        assets_mask = ~liabilities_mask
        assets_val = df_all[assets_mask]['Market_Value'].sum()
        liabilities_val = df_all[liabilities_mask]['Market_Value'].sum()
        g_cost = df_all[assets_mask]['Total_Cost'].sum()

    g_pl = df_all['Unrealized_PL'].sum()
    g_roi = (g_pl / g_cost * 100) if g_cost > 0 else 0

    render_hud_kpi(total_val, assets_val, liabilities_val, g_pl, g_roi, c_symbol)
    
    st.markdown("---")

    # 2. Main Visuals
    c_main_1, c_main_2, c_main_3 = st.columns([1.5, 1.2, 0.8])
    
    with c_main_1:
        st.markdown("##### 🧬 Asset Allocation")
        render_sunburst_allocation(df_all, total_val)
        
    with c_main_2:
        st.markdown("##### 📈 Wealth Trend")
        history = st.session_state.get("history_data", [])
        render_mini_trend(history, c_symbol)
        
        st.markdown("##### 🏥 Health Check")
        render_health_monitor(assets_val, liabilities_val, c_symbol)

    with c_main_3:
        # Quick Top Movers
        st.markdown("##### 🔥 Top Movers")
        if not df_all.empty:
            df_movers = df_all.sort_values("ROI (%)", ascending=False).head(4)
            for _, row in df_movers.iterrows():
                roi = row['ROI (%)']
                color = "#00B4D8" if roi > 0 else "#FF0055"
                safe_ticker = html.escape(str(row['Ticker']))
                st.markdown(f"""
                <div style="background: rgba(255,255,255,0.05); padding: 8px; border-radius: 6px; margin-bottom: 8px; display: flex; justify-content: space-between;">
                    <span style="font-weight: bold; font-size: 0.9rem;">{safe_ticker}</span>
                    <span style="color: {color}; font-weight: bold;">{roi:+.1f}%</span>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("---")
    
    # 3. Accounts & Breakdown
    render_account_cards(df_all, c_symbol)
