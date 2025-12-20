"""
Dashboard UI components.

This module provides UI rendering functions for the investment dashboard,
including KPIs, rebalancing analysis, and portfolio details.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import Optional

from config import get_config

config = get_config()


def render_dashboard(df_all: pd.DataFrame, c_symbol: str, total_val: float) -> None:
    """
    Render the main dashboard view.
    
    Args:
        df_all: DataFrame with market data for all assets
        c_symbol: Currency symbol for display
        total_val: Total portfolio value
    """
    if df_all.empty:
        st.info("目前無資產數據，請前往管理頁面新增。")
        return

    # 1. KPI 區塊
    st.markdown("### 🏆 總資產概況 (Net Worth)")
    # For KPIs, we use the Base Currency (total_val is already Net Worth in Base)
    # But we might want to separate Assets and Liabilities
    
    # Calculate Total Assets (Positive Net Value) and Total Liabilities (Negative Net Value) (approx)
    # Better: Filter by Type
    assets_val = df_all[df_all['Type'] != '負債']['Market_Value'].sum()
    liabilities_val = df_all[df_all['Type'] == '負債']['Market_Value'].sum()
    
    # Total Cost logic:
    # Assets Cost is positive. Liabilities Cost (Principal) is positive in data, but debts.
    # KPI Logic: 
    # Net Worth = Assets - Liabilities.
    # Total Invested = Assets Cost.
    # Liability Principal is separate.
    
    g_cost = df_all[df_all['Type'] != '負債']['Total_Cost'].sum()
    g_pl = df_all['Unrealized_PL'].sum() # PL of Assets + PL of Liabilities
    g_roi = (g_pl / g_cost) * 100 if g_cost > 0 else 0
    
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("淨資產", f"{c_symbol}{total_val:,.0f}", help=f"資產: {c_symbol}{assets_val:,.0f} | 負債: {c_symbol}{liabilities_val:,.0f}")
    kpi2.metric("總投入成本", f"{c_symbol}{g_cost:,.0f}", help="(僅計算資產端)")
    kpi3.metric("總損益", f"{c_symbol}{g_pl:,.0f}", delta_color="normal")
    kpi4.metric("總報酬率 (ROI)", f"{g_roi:.2f}%", delta=f"{g_roi:.2f}%")
    
    st.divider()

    # 2. 再平衡分析
    render_rebalancing(df_all, total_val, c_symbol)
    st.divider()

    # 3. 持股明細 (核心修改)
    render_holdings_section(df_all, total_val, c_symbol)


def render_rebalancing(df_all: pd.DataFrame, total_val: float, c_symbol: str) -> None:
    """
    Render asset allocation and rebalancing analysis.
    
    Args:
        df_all: DataFrame with market data
        total_val: Total portfolio value
        c_symbol: Currency symbol
    """
    st.markdown("### ⚖️ 資產配置與再平衡")
    
    current_alloc = df_all.groupby('Type')['Market_Value'].sum()
    current_alloc_pct = (current_alloc / total_val * 100).reset_index()
    current_alloc_pct.columns = ['Type', 'Current_Pct']
    
    targets = st.session_state.allocation_targets
    target_df = pd.DataFrame(list(targets.items()), columns=['Type', 'Target_Pct'])
    
    alloc_df = pd.merge(target_df, current_alloc_pct, on='Type', how='outer').fillna(0)
    alloc_df['Diff'] = alloc_df['Current_Pct'] - alloc_df['Target_Pct']
    
    col1, col2 = st.columns([2, 1])
    with col1:
        colors = config.ui.colors
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=alloc_df['Type'], 
            y=alloc_df['Current_Pct'], 
            name='目前佔比', 
            marker_color=colors['primary_bar']
        ))
        fig.add_trace(go.Bar(
            x=alloc_df['Type'], 
            y=alloc_df['Target_Pct'], 
            name='目標佔比', 
            marker_color=colors['secondary_bar']
        ))
        fig.update_layout(barmode='group', height=250, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.write("**📊 建議操作**")
        tolerance = config.ui.allocation_tolerance_pct
        for idx, row in alloc_df.iterrows():
            diff = row['Diff']
            if diff < -tolerance:
                st.markdown(f"🔵 **{row['Type']}**: <span style='color:green'>不足 {abs(diff):.1f}%</span>", unsafe_allow_html=True)
            elif diff > tolerance:
                st.markdown(f"🟠 **{row['Type']}**: <span style='color:red'>超額 {abs(diff):.1f}%</span>", unsafe_allow_html=True)
            else:
                st.markdown(f"⚪ **{row['Type']}**: 準確")


def render_holdings_section(df_all: pd.DataFrame, total_val: float, c_symbol: str) -> None:
    """
    Render portfolio holdings section with filtering.
    
    Args:
        df_all: DataFrame with market data
        total_val: Total portfolio value
        c_symbol: Currency symbol
    """
    st.markdown("### 📉 投資組合明細")
    
    # 篩選器
    available_types = ["全部"] + list(df_all['Type'].unique())
    selected_view = st.radio("選擇檢視模式：", available_types, horizontal=True, label_visibility="collapsed")
    
    st.markdown("---")
    
    if selected_view == "全部":
        # 模式 A: 顯示「各大類別」的總覽
        render_category_overview(df_all, total_val, c_symbol)
    else:
        # 模式 B: 顯示「特定類別」內的個股明細
        render_single_category_detail(df_all, total_val, c_symbol, selected_view)


def render_category_overview(df_all: pd.DataFrame, total_val: float, c_symbol: str) -> None:
    """
    Render overview of all asset categories.
    
    Args:
        df_all: DataFrame with market data
        total_val: Total portfolio value
        c_symbol: Currency symbol
    """
    # Group by Type and calculate metrics
    df_grouped = df_all.groupby('Type').agg({
        'Market_Value': 'sum',
        'Total_Cost': 'sum',
        'Unrealized_PL': 'sum'
    }).reset_index()
    
    # 計算 ROI
    df_grouped['ROI'] = df_grouped.apply(
        lambda x: (x['Unrealized_PL'] / x['Total_Cost'] * 100) if x['Total_Cost'] > 0 else 0, axis=1
    )
    
    # 左右佈局
    col_list, col_charts = st.columns([0.65, 0.35], gap="large")
    
    # 左側：顯示各大類別的卡片
    with col_list:
        # 表頭
        h1, h2, h3 = st.columns([1.5, 1.2, 1.2])
        h1.markdown("**資產類別**")
        h2.caption("類別市值 & 佔比")
        h3.caption("類別總損益 & ROI")
        st.divider()
        
        for idx, row in df_grouped.iterrows():
            type_weight = (row['Market_Value'] / total_val) * 100 if total_val > 0 else 0
            
            with st.container():
                c1, c2, c3 = st.columns([1.5, 1.2, 1.2])
                with c1:
                    st.subheader(f"📂 {row['Type']}")
                
                with c2:
                    # Logic for Display Value (Native vs Base) is tricky for Category Aggregation.
                    # Category Sum implies Base Currency always, because you can't sum mixed currencies.
                    # So Overview always uses Base Currency.
                    st.markdown(f"**{c_symbol}{row['Market_Value']:,.0f}**")
                    st.progress(min(type_weight / 100, 1.0))
                    st.caption(f"全資產佔比: {type_weight:.1f}%")
                    
                with c3:
                    pl_color = "green" if row['Unrealized_PL'] > 0 else "red"
                    st.markdown(f"<span style='color:{pl_color}; font-weight:bold'>{c_symbol}{row['Unrealized_PL']:,.0f}</span>", unsafe_allow_html=True)
                    
                    roi_bg = "#e6fffa" if row['ROI'] > 0 else "#fff5f5"
                    roi_color = "#009688" if row['ROI'] > 0 else "#e53e3e"
                    st.markdown(
                        f"<div style='background-color:{roi_bg}; color:{roi_color}; padding:4px; border-radius:4px; text-align:center; width:80%; font-size:12px; font-weight:bold'>"
                        f"{row['ROI']:.1f}%</div>", 
                        unsafe_allow_html=True
                    )
            st.divider()

    # 右側：顯示資產分佈圖 (Pie Chart of Types)
    with col_charts:
        st.markdown("**📊 資產配置全貌**")
        fig_pie = px.pie(df_grouped, values='Market_Value', names='Type', hole=0.5)
        fig_pie.update_layout(
            margin=dict(t=0, b=0, l=0, r=0),
            height=250,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig_pie, use_container_width=True)
        
        st.markdown("**📈 類別績效比較**")
        fig_bar = px.bar(df_grouped, x='ROI', y='Type', orientation='h', color='ROI', color_continuous_scale='RdYlGn')
        fig_bar.update_layout(xaxis_title=None, yaxis_title=None, height=200, margin=dict(t=0,b=0,l=0,r=0), coloraxis_showscale=False)
        st.plotly_chart(fig_bar, use_container_width=True)


def render_single_category_detail(df_all: pd.DataFrame, total_val: float, c_symbol: str, category: str) -> None:
    """
    Render detailed view of a single asset category.
    
    Args:
        df_all: DataFrame with market data
        total_val: Total portfolio value
        c_symbol: Currency symbol
        category: Asset category to display
    """
    # Filter data
    cat_df = df_all[df_all['Type'] == category]
    
    if cat_df.empty:
        st.warning("此類別無資料")
        return

    cat_val = cat_df['Market_Value'].sum()
    cat_pct = (cat_val / total_val) * 100 if total_val > 0 else 0

    st.markdown(f"#### 📂 {category} 明細 (總值: {c_symbol}{cat_val:,.0f} | 佔比: {cat_pct:.1f}%)")

    # 左右佈局
    col_list, col_charts = st.columns([0.65, 0.35], gap="large")

    # 左側：個股清單
    with col_list:
        h1, h2, h3 = st.columns([1.5, 1.2, 1.2])
        h1.caption("資產名稱")
        h2.caption("市值 & 類別權重")
        h3.caption("損益 & 績效")
        st.markdown("---")

        for idx, row in cat_df.iterrows():
            weight_in_cat = (row['Market_Value'] / cat_val) * 100 if cat_val > 0 else 0
            
            with st.container():
                c1, c2, c3 = st.columns([1.5, 1.2, 1.2])
                
                with c1:
                    st.markdown(f"**{row['Ticker']}**")
                    status_color = "green" if "即時" in row['Status'] else "#FF4B4B"
                    st.caption(f"持倉: {row['Quantity']:,.2f} | 均價: {row['Avg_Cost']:,.0f}")
                    st.markdown(f"<span style='background-color:{status_color}; color:white; padding:1px 4px; border-radius:3px; font-size:10px'>{row['Status']}</span>", unsafe_allow_html=True)
                    # Display last update time
                    last_update = row.get('Last_Update', 'N/A')
                    st.caption(f"🕒 更新: {last_update}")
                
                with c2:
                    # Use Display Columns if available
                    d_mv = row.get("Display_Market_Value", row['Market_Value'])
                    d_curr = row.get("Display_Currency", row.get("Currency", "USD"))
                    d_sym = config.ui.currency_symbols.get(d_curr, "$")
                    d_price = row.get("Display_Price", row['Current_Price'])
                    
                    st.markdown(f"**{d_sym}{d_mv:,.0f}**")
                    st.caption(f"現價: {d_price:,.2f}")
                    st.progress(min(weight_in_cat / 100, 1.0))
                    st.caption(f"類別佔比: {weight_in_cat:.0f}%") # 這是個股在該類別的佔比

                with c3:
                    d_pl = row.get("Display_PL", row['Unrealized_PL'])
                    pl_c = "green" if d_pl > 0 else "red"
                    st.markdown(f"<span style='color:{pl_c}; font-weight:bold'>{d_sym}{d_pl:,.0f}</span>", unsafe_allow_html=True)
                    roi_bg = "#e6fffa" if row['ROI (%)'] > 0 else "#fff5f5"
                    roi_color = "#009688" if row['ROI (%)'] > 0 else "#e53e3e"
                    st.markdown(f"<div style='background-color:{roi_bg}; color:{roi_color}; padding:4px; border-radius:4px; text-align:center; width:80%; font-size:12px; font-weight:bold'>{row['ROI (%)']:.1f}%</div>", unsafe_allow_html=True)
            st.divider()

    # 右側：個股分析圖表
    with col_charts:
        st.markdown(f"**📊 {category} 權重分佈**")
        fig_pie = px.pie(cat_df, values='Market_Value', names='Ticker', hole=0.5)
        fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=200, legend=dict(orientation="h", yanchor="bottom", y=-0.2))
        st.plotly_chart(fig_pie, use_container_width=True)
        
        st.markdown(f"**📈 {category} 個股排行**")
        df_sorted = cat_df.sort_values('ROI (%)', ascending=True)
        fig_bar = px.bar(df_sorted, x='ROI (%)', y='Ticker', orientation='h', color='ROI (%)', color_continuous_scale='RdYlGn', text='ROI (%)')
        fig_bar.update_layout(xaxis_title=None, yaxis_title=None, showlegend=False, height=250, margin=dict(t=0,b=0,l=0,r=0), coloraxis_showscale=False)
        fig_bar.update_traces(texttemplate='%{text:.1f}%', textposition='inside')
        st.plotly_chart(fig_bar, use_container_width=True)