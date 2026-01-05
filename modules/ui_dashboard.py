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
from modules.data_loader import save_snapshot

config = get_config()


def render_asset_liability_ratio(df_all: pd.DataFrame, assets_val: float, liabilities_val: float, c_symbol: str) -> None:
    """
    Render asset/liability ratio analysis.
    
    Args:
        df_all: DataFrame with market data
        assets_val: Total assets value
        liabilities_val: Total liabilities value
        c_symbol: Currency symbol
    """
    st.markdown("### 💹 資產負債比分析")
    
    # Calculate ratio
    abs_liabilities = abs(liabilities_val)
    asset_liability_ratio = assets_val / abs_liabilities if abs_liabilities > 0 else float('inf')
    debt_to_asset_ratio = abs_liabilities / assets_val if assets_val > 0 else 0
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        st.metric(
            "總資產",
            f"{c_symbol}{assets_val:,.0f}",
            help="所有資產的市值總和"
        )
    
    with col2:
        st.metric(
            "總負債",
            f"{c_symbol}{abs_liabilities:,.0f}",
            help="所有負債的金額總和"
        )
    
    with col3:
        # Determine health status
        if abs_liabilities == 0:
            ratio_display = "無負債"
            ratio_color = "green"
        elif asset_liability_ratio >= 2.0:
            ratio_display = f"{asset_liability_ratio:.2f}:1"
            ratio_color = "green"
        elif asset_liability_ratio >= 1.0:
            ratio_display = f"{asset_liability_ratio:.2f}:1"
            ratio_color = "orange"
        else:
            ratio_display = f"{asset_liability_ratio:.2f}:1"
            ratio_color = "red"
        
        st.markdown(f"""
        <div class="css-card" style="text-align: center;">
            <div style='color: #cbd5e1; font-size: 0.9em;'>資產負債比</div>
            <div style='font-size: 1.8em; font-weight: bold; color: {ratio_color}; margin: 5px 0;'>{ratio_display}</div>
            <div style='color: #94a3b8; font-size: 0.75em;'>負債佔資產比: {debt_to_asset_ratio*100:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Visual representation
    if abs_liabilities > 0:
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            # Pie chart
            fig_pie = go.Figure(data=[go.Pie(
                labels=['資產', '負債'],
                values=[assets_val, abs_liabilities],
                marker_colors=['#4CAF50', '#F44336'],
                hole=0.4
            )])
            fig_pie.update_layout(
                title="資產 vs 負債",
                margin=dict(t=40, b=0, l=0, r=0),
                height=200,
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5)
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col_chart2:
            # Bar chart comparison
            fig_bar = go.Figure(data=[
                go.Bar(name='金額', x=['資產', '負債'], y=[assets_val, abs_liabilities],
                       marker_color=['#4CAF50', '#F44336'])
            ])
            fig_bar.update_layout(
                title="金額比較",
                yaxis_title=f"金額 ({c_symbol})",
                margin=dict(t=40, b=0, l=0, r=0),
                height=200,
                showlegend=False
            )
            st.plotly_chart(fig_bar, use_container_width=True)


def render_account_breakdown(df_all: pd.DataFrame, c_symbol: str) -> None:
    """
    Render account breakdown section.
    
    Args:
        df_all: DataFrame with market data
        c_symbol: Currency symbol
    """
    st.markdown("### 🏦 各帳戶資產概覽")
    
    # Get accounts from session state
    accounts = st.session_state.get("accounts", [])
    
    if not accounts:
        st.info("尚未設定帳戶。請至「管理設定」頁面新增帳戶。")
        return
    
    # Map account IDs to names
    account_map = {
        acc.get("account_id") or acc.get("id"): acc.get("name")
        for acc in accounts
    }
    
    # Calculate totals by account
    # df_all should have Account_ID or we need to merge from portfolio
    portfolio = st.session_state.get("portfolio", [])
    
    # Create mapping of Ticker to Account_ID
    ticker_to_account = {}
    for asset in portfolio:
        ticker = asset.get("symbol") or asset.get("Ticker")
        acc_id = asset.get("account_id") or asset.get("Account_ID", "default_main")
        ticker_to_account[ticker] = acc_id
    
    # Add Account_ID to df_all if not present
    if "Account_ID" not in df_all.columns:
        df_all["Account_ID"] = df_all["Ticker"].map(ticker_to_account).fillna("default_main")
    
    # Group by account
    account_totals = df_all.groupby("Account_ID").agg({
        "Net_Value": "sum",
        "Market_Value": "sum",
        "Total_Cost": "sum",
        "Unrealized_PL": "sum"
    }).reset_index()
    
    # Calculate total for percentage
    total_all_accounts = account_totals["Net_Value"].sum()
    
    # Display account cards
    num_accounts = len(account_totals)
    cols_per_row = 3
    
    for i in range(0, num_accounts, cols_per_row):
        cols = st.columns(cols_per_row)
        for j in range(cols_per_row):
            idx = i + j
            if idx < num_accounts:
                row = account_totals.iloc[idx]
                acc_id = row["Account_ID"]
                acc_name = account_map.get(acc_id, "未知帳戶")
                acc_value = row["Net_Value"]
                acc_cost = row["Total_Cost"]
                acc_pl = row["Unrealized_PL"]
                acc_roi = (acc_pl / acc_cost * 100) if acc_cost > 0 else 0
                acc_pct = (acc_value / total_all_accounts * 100) if total_all_accounts > 0 else 0
                
                with cols[j]:
                    pl_color = "#4ade80" if acc_pl >= 0 else "#f87171"
                    roi_color = "#34d399" if acc_roi >= 0 else "#f87171"
                    
                    st.markdown(f"""
                    <div class="css-card">
                        <div style='font-size: 1.1em; font-weight: bold; margin-bottom: 5px; color: #f1f5f9;'>🏦 {acc_name}</div>
                        <div style='font-size: 1.5em; font-weight: bold; color: #818cf8; margin: 5px 0;'>{c_symbol}{acc_value:,.0f}</div>
                        <div style='color: #94a3b8; font-size: 0.85em; margin-bottom: 5px;'>佔比: {acc_pct:.1f}%</div>
                        <div style='color: {pl_color}; font-size: 0.9em; font-weight: bold;'>損益: {c_symbol}{acc_pl:,.0f}</div>
                        <div style='color: {roi_color}; font-size: 0.9em;'>ROI: {acc_roi:+.1f}%</div>
                    </div>
                    """, unsafe_allow_html=True)
    
    # Summary chart
    st.divider()
    col_summary1, col_summary2 = st.columns(2)
    
    with col_summary1:
        # Account distribution pie
        account_totals["Account_Name"] = account_totals["Account_ID"].map(account_map)
        fig_acc_pie = px.pie(
            account_totals,
            values="Market_Value",
            names="Account_Name",
            title="帳戶資產分佈",
            hole=0.4
        )
        fig_acc_pie.update_layout(
            margin=dict(t=40, b=0, l=0, r=0),
            height=250
        )
        st.plotly_chart(fig_acc_pie, use_container_width=True)
    
    with col_summary2:
        # Account ROI comparison
        account_totals["ROI"] = account_totals.apply(
            lambda x: (x["Unrealized_PL"] / x["Total_Cost"] * 100) if x["Total_Cost"] > 0 else 0,
            axis=1
        )
        fig_acc_roi = px.bar(
            account_totals,
            x="ROI",
            y="Account_Name",
            orientation="h",
            title="帳戶績效比較",
            color="ROI",
            color_continuous_scale="RdYlGn"
        )
        fig_acc_roi.update_layout(
            xaxis_title="ROI (%)",
            yaxis_title=None,
            margin=dict(t=40, b=0, l=0, r=0),
            height=250,
            coloraxis_showscale=False
        )
        st.plotly_chart(fig_acc_roi, use_container_width=True)


def render_dashboard(df_all: pd.DataFrame, c_symbol: str, total_val: float, exchange_rate: float = 32.5) -> None:
    """
    Render the main dashboard view.
    
    Args:
        df_all: DataFrame with market data for all assets
        c_symbol: Currency symbol for display
        total_val: Total portfolio value
        exchange_rate: USD to TWD exchange rate
    """
    if df_all.empty:
        st.info("目前無資產數據，請前往管理頁面新增。")
        return

    # 0. Snapshot Button
    c1, c2 = st.columns([0.8, 0.2])
    with c2:
        if st.button("📸 儲存今日快照", use_container_width=True, help="儲存當前總資產快照至歷史紀錄"):
            # Calculate breakdown
            breakdown = df_all.groupby('Type')['Market_Value'].sum().to_dict()
            
            # Determine TWD/USD total
            # Assumes total_val is in Display Currency
            is_usd = "$" in c_symbol and "NT" not in c_symbol
            
            if is_usd:
                tot_usd = total_val
                tot_twd = total_val * exchange_rate
            else:
                tot_twd = total_val
                tot_usd = total_val / exchange_rate if exchange_rate > 0 else 0
                
            # Adjust breakdown to base if needed (breakdown computed from displayed df_all)
            # If display is USD, breakdown is USD. save_snapshot expects 'value' (doesn't specify curr, but HistoryRecord has TWD/USD totals).
            # The breakdown fields in HistoryRecord are us_stock_val, etc. usually in base currency (TWD).
            # We should standardize breakdown to TWD for consistency or store both?
            # Creating a simple map: Type -> TWD Value
            breakdown_twd = {}
            for k, v in breakdown.items():
                if is_usd:
                    breakdown_twd[k] = v * exchange_rate
                else:
                    breakdown_twd[k] = v
                    
            save_snapshot(tot_twd, tot_usd, breakdown_twd)
            st.success("已儲存快照！")
            
    # 0.5 History Chart (replaced with advanced charts selector)
    if "history_data" in st.session_state and st.session_state.history_data:
        with st.expander("📈 歷史趨勢", expanded=False):
            render_history_chart(st.session_state.history_data, c_symbol)
    
    # 0.6 Advanced Charts Section (NEW)
    with st.expander("📊 進階圖表分析", expanded=True):
        render_advanced_charts_section(df_all, total_val, c_symbol, exchange_rate)

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
    
    # Custom Card KPI Layout
    cols = st.columns(4)

    metrics = [
        {
            "label": "淨資產 (Net Worth)",
            "value": f"{c_symbol}{total_val:,.0f}",
            "sub": f"資產: {c_symbol}{assets_val:,.0f} | 負債: {c_symbol}{liabilities_val:,.0f}",
            "color": "#5D69B1"
        },
        {
            "label": "總投入成本 (Cost)",
            "value": f"{c_symbol}{g_cost:,.0f}",
            "sub": "僅計算資產端投入",
            "color": "#E58606"
        },
        {
            "label": "總損益 (P/L)",
            "value": f"{c_symbol}{g_pl:,.0f}",
            "sub": "含未實現損益",
            "color": "green" if g_pl >= 0 else "red"
        },
        {
            "label": "總報酬率 (ROI)",
            "value": f"{g_roi:+.2f}%",
            "sub": "基於總成本計算",
            "color": "green" if g_roi >= 0 else "red"
        }
    ]

    for i, m in enumerate(metrics):
        with cols[i]:
            st.markdown(f"""
            <div class="css-card">
                <div style="color: #666; font-size: 0.9em; margin-bottom: 5px;">{m['label']}</div>
                <div style="font-size: 1.8em; font-weight: bold; color: {m['color']};">{m['value']}</div>
                <div style="color: #999; font-size: 0.8em; margin-top: 5px;">{m['sub']}</div>
            </div>
            """, unsafe_allow_html=True)
    
    st.divider()

    # 2. Asset/Liability Ratio (新增)
    render_asset_liability_ratio(df_all, assets_val, liabilities_val, c_symbol)
    st.divider()

    # 3. Account Breakdown (新增)
    render_account_breakdown(df_all, c_symbol)
    st.divider()

    # 4. 再平衡分析
    render_rebalancing(df_all, total_val, c_symbol)
    st.divider()

    # 5. 持股明細
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
        fig.update_layout(
            barmode='group',
            height=250,
            margin=dict(l=20, r=20, t=20, b=20),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
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
        'Net_Value': 'sum',
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
                    # So Overview always uses Base Currency. Net_Value can be negative for Liabilities.
                    val = row['Net_Value']
                    val_color = "#f87171" if val < 0 else None
                    val_style = f"color: {val_color};" if val_color else ""
                    
                    st.markdown(f"**<span style='{val_style}'>{c_symbol}{val:,.0f}</span>**", unsafe_allow_html=True)
                    # For progress bar, we take absolute contribution or handle standard logic
                    # If total_val (Net Worth) is positive, and this is liability, implicit weight is negative?
                    # Streamlit progress bar needs 0.0-1.0
                    
                    safe_weight = abs(type_weight) # Use absolute for visual bar
                    st.progress(min(safe_weight / 100, 1.0))
                    st.caption(f"全資產佔比: {type_weight:.1f}%")
                    
                with c3:
                    pl_color = "#4ade80" if row['Unrealized_PL'] >= 0 else "#f87171"
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
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
        )
        st.plotly_chart(fig_pie, use_container_width=True)
        
        st.markdown("**📈 類別績效比較**")
        fig_bar = px.bar(df_grouped, x='ROI', y='Type', orientation='h', color='ROI', color_continuous_scale='RdYlGn')
        fig_bar.update_layout(
            xaxis_title=None,
            yaxis_title=None,
            height=200,
            margin=dict(t=0,b=0,l=0,r=0),
            coloraxis_showscale=False,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
        )
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
    cat_df = df_all[df_all['Type'] == category].copy()
    
    if cat_df.empty:
        st.warning("此類別無資料")
        return

    cat_val = cat_df['Market_Value'].sum()
    cat_pct = (cat_val / total_val) * 100 if total_val > 0 else 0

    st.markdown(f"#### 📂 {category} 明細 (總值: {c_symbol}{cat_val:,.0f} | 佔比: {cat_pct:.1f}%)")

    # 左右佈局
    col_list, col_charts = st.columns([0.65, 0.35], gap="large")

    # 左側：個股清單 (改用 DataFrame)
    with col_list:
        # Prepare data for st.dataframe

        # Calculate Category Weight in advance
        cat_df['Cat_Weight'] = cat_df['Market_Value'] / cat_val if cat_val > 0 else 0

        # Format columns for display
        display_df = cat_df.copy()

        # Select and Rename columns
        display_df = display_df[[
            'Ticker', 'Quantity', 'Avg_Cost', 'Current_Price',
            'Net_Value', 'Unrealized_PL', 'ROI (%)', 'Cat_Weight', 'Status', 'Last_Update'
        ]]

        # We need to ensure types are numeric for column_config to work
        # Ticker: Text
        # Quantity, Avg_Cost, Current_Price: Number
        # Net_Value, Unrealized_PL: Currency
        # ROI, Cat_Weight: Number (Percentage)

        st.dataframe(
            display_df,
            key="dashboard_holdings_table",
            column_config={
                "Ticker": st.column_config.TextColumn("代號", width="small", pinned=True),
                "Quantity": st.column_config.NumberColumn("持倉", format="%.2f"),
                "Avg_Cost": st.column_config.NumberColumn("成本", format="%.2f"),
                "Current_Price": st.column_config.NumberColumn("現價", format="%.2f"),
                "Net_Value": st.column_config.NumberColumn(
                    f"淨值 ({c_symbol})",
                    format=f"{c_symbol}%.0f"
                ),
                "Unrealized_PL": st.column_config.NumberColumn(
                    f"損益 ({c_symbol})",
                    format=f"{c_symbol}%.0f"
                ),
                "ROI (%)": st.column_config.ProgressColumn(
                    "ROI",
                    format="%.1f%%",
                    min_value=-50,
                    max_value=50,
                ),
                "Cat_Weight": st.column_config.ProgressColumn(
                    "類別佔比",
                    format="%.1f%%",
                    min_value=0,
                    max_value=1,
                ),
                "Status": st.column_config.TextColumn("狀態", width="small"),
                "Last_Update": st.column_config.TextColumn("更新時間", width="medium"),
            },
            hide_index=True,
            width="stretch",
            height=500
        )

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

def render_history_chart(history: list, c_symbol: str):
    """Render Net Worth History chart."""
    if not history:
        return
        
    df = pd.DataFrame(history)
    if df.empty:
        return
        
    # Line Chart: Total Net Worth
    # Choose column based on symbol
    y_col = "total_net_worth_usd" if "$" in c_symbol and "NT" not in c_symbol else "total_net_worth_twd"
    
    fig = px.line(df, x='date', y=y_col, title='總資產成長趨勢', markers=True)
    fig.update_layout(
        xaxis_title="日期",
        yaxis_title=f"總值 ({c_symbol})",
        height=300,
        margin=dict(l=20, r=20, t=40, b=20),
        plot_bgcolor='rgba(0,0,0,0)',
    )
    st.plotly_chart(fig, width="stretch")
    
    # Stacked Area: Asset Classes
    cols = ["us_stock_val", "tw_stock_val", "cash_val", "crypto_val", "loan_val"]
    cols = [c for c in cols if c in df.columns]
    
    if cols:
        fig_area = px.area(df, x='date', y=cols, title='資產類別堆疊圖')
        fig_area.update_layout(
            xaxis_title="日期",
            yaxis_title="價值 (TWD)",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            plot_bgcolor='rgba(0,0,0,0)',
        )
        st.plotly_chart(fig_area, use_container_width=True)


# ===========================
# Advanced Charts - Phase 1
# ===========================

def render_enhanced_networth_chart(history: list, c_symbol: str):
    """Enhanced net worth growth chart with moving averages and targets."""
    if not history or len(history) < 2:
        st.info("需要至少 2 個歷史快照才能顯示增強版趨勢圖")
        return
    
    df = pd.DataFrame(history)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    
    y_col = "total_net_worth_usd" if "$" in c_symbol and "NT" not in c_symbol else "total_net_worth_twd"
    
    # Calculate moving averages
    if len(df) >= 7:
        df['MA7'] = df[y_col].rolling(window=7, min_periods=1).mean()
    if len(df) >= 30:
        df['MA30'] = df[y_col].rolling(window=30, min_periods=1).mean()
    
    # Create figure with secondary y-axis for ROI
    fig = go.Figure()
    
    # Main line - Net Worth
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df[y_col],
        mode='lines+markers',
        name='淨資產',
        line=dict(color='#5D69B1', width=3),
        marker=dict(size=6),
        hovertemplate='%{y:,.0f}<extra></extra>'
    ))
    
    # Moving averages
    if 'MA7' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['MA7'],
            mode='lines',
            name='7日均線',
            line=dict(color='#E58606', width=2, dash='dash'),
            hovertemplate='%{y:,.0f}<extra></extra>'
        ))
    
    if 'MA30' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['MA30'],
            mode='lines',
            name='30日均線',
            line=dict(color='#52BCA3', width=2, dash='dot'),
            hovertemplate='%{y:,.0f}<extra></extra>'
        ))
    
    # Add target line (example: 1.5x current value)
    current_val = df[y_col].iloc[-1]
    target_val = current_val * 1.5
    fig.add_hline(
        y=target_val,
        line_dash="dash",
        line_color="gold",
        annotation_text=f"目標: {c_symbol}{target_val:,.0f}",
        annotation_position="right"
    )
    
    fig.update_layout(
        title='📈 淨資產成長趨勢（增強版）',
        xaxis_title='日期',
        yaxis_title=f'淨資產 ({c_symbol})',
        hovermode='x unified',
        height=450,
        template='plotly_white',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Stats summary
    col1, col2, col3, col4 = st.columns(4)
    total_return = ((df[y_col].iloc[-1] / df[y_col].iloc[0]) - 1) * 100 if df[y_col].iloc[0] > 0 else 0
    peak_val = df[y_col].max()
    current_drawdown = ((df[y_col].iloc[-1] / peak_val) - 1) * 100 if peak_val > 0 else 0
    
    col1.metric("總報酬", f"{total_return:+.2f}%")
    col2.metric("歷史高點", f"{c_symbol}{peak_val:,.0f}")
    col3.metric("當前回撤", f"{current_drawdown:.2f}%", delta=f"{current_drawdown:.2f}%")
    col4.metric("數據點數", f"{len(df)} 個快照")


def render_allocation_radar_chart(df_all: pd.DataFrame, total_val: float):
    """Allocation radar chart comparing target vs actual allocation."""
    if df_all.empty:
        st.info("無資產數據")
        return
    
    # Get current allocation
    current_alloc = df_all.groupby('Type')['Market_Value'].sum()
    current_alloc_pct = (current_alloc / total_val * 100) if total_val > 0 else pd.Series()
    
    # Get targets
    targets = st.session_state.allocation_targets
    
    # Combine all categories
    all_categories = list(set(list(targets.keys()) + list(current_alloc_pct.index)))
    
    target_values = [targets.get(cat, 0) for cat in all_categories]
    actual_values = [current_alloc_pct.get(cat, 0) for cat in all_categories]
    
    # Create radar chart
    fig = go.Figure()
    
    # Target allocation
    fig.add_trace(go.Scatterpolar(
        r=target_values,
        theta=all_categories,
        fill='toself',
        name='目標配置',
        line=dict(color='#E58606', width=2, dash='dash'),
        fillcolor='rgba(229, 134, 6, 0.1)'
    ))
    
    # Actual allocation
    fig.add_trace(go.Scatterpolar(
        r=actual_values,
        theta=all_categories,
        fill='toself',
        name='實際配置',
        line=dict(color='#5D69B1', width=3),
        fillcolor='rgba(93, 105, 177, 0.3)'
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, max(max(target_values + actual_values, default=0) * 1.2, 10)]
            )
        ),
        showlegend=True,
        title='🕸️ 資產配置雷達圖（目標 vs 實際）',
        height=500,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.1,
            xanchor="center",
            x=0.5
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Deviation summary
    st.markdown("#### 配置偏離度")
    deviation_data = []
    for cat in all_categories:
        target = targets.get(cat, 0)
        actual = current_alloc_pct.get(cat, 0)
        deviation = actual - target
        deviation_data.append({
            "類別": cat,
            "目標 %": f"{target:.1f}%",
            "實際 %": f"{actual:.1f}%",
            "偏離": f"{deviation:+.1f}%",
            "狀態": "✅ 達標" if abs(deviation) <= 5 else ("🔵 不足" if deviation < 0 else "🟠 超配")
        })
    
    df_deviation = pd.DataFrame(deviation_data)
    st.dataframe(df_deviation, use_container_width=True, hide_index=True)


def render_top10_holdings_dashboard(df_all: pd.DataFrame, c_symbol: str):
    """Top 10 holdings performance dashboard with mini charts."""
    if df_all.empty:
        st.info("無資產數據")
        return
    
    # Filter and sort
    df_top = df_all.nlargest(10, 'Market_Value').copy()
    
    st.markdown("### 🏆 Top 10 持倉績效儀表板")
    
    # Create cards in rows of 2
    for i in range(0, len(df_top), 2):
        cols = st.columns(2)
        for j in range(2):
            idx = i + j
            if idx < len(df_top):
                row = df_top.iloc[idx]
                with cols[j]:
                    # Determine colors
                    roi = row.get('ROI (%)', 0)
                    pl = row.get('Unrealized_PL', 0)
                    roi_color = "green" if roi >= 0 else "red"
                    pl_color = "green" if pl >= 0 else "red"
                    
                    # Rank badge
                    rank = idx + 1
                    badge_color = "#FFD700" if rank == 1 else ("#C0C0C0" if rank == 2 else ("#CD7F32" if rank == 3 else "#5D69B1"))
                    
                    st.markdown(f"""
                    <div class="css-card" style="border: 2px solid {badge_color}; margin-bottom: 10px;">
                        <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;'>
                            <div>
                                <span style='background-color: {badge_color}; color: white; padding: 4px 8px; border-radius: 5px; font-weight: bold; margin-right: 8px;'>#{rank}</span>
                                <span style='font-size: 1.2em; font-weight: bold; color: #f1f5f9;'>{row.get('Ticker', 'N/A')}</span>
                            </div>
                            <div style='text-align: right;'>
                                <div style='font-size: 0.85em; color: #94a3b8;'>{row.get('Type', 'N/A')}</div>
                            </div>
                        </div>
                        <div style='margin: 10px 0;'>
                            <div style='font-size: 1.4em; font-weight: bold; color: #818cf8;'>{c_symbol}{row.get('Market_Value', 0):,.0f}</div>
                            <div style='font-size: 0.85em; color: #94a3b8;'>持倉: {row.get('Quantity', 0):.2f} | 成本: {row.get('Avg_Cost', 0):.2f}</div>
                        </div>
                        <div style='display: flex; justify-content: space-between; margin-top: 10px;'>
                            <div>
                                <div style='font-size: 0.8em; color: #94a3b8;'>損益</div>
                                <div style='font-size: 1.1em; font-weight: bold; color: {pl_color};'>{c_symbol}{pl:,.0f}</div>
                            </div>
                            <div style='text-align: right;'>
                                <div style='font-size: 0.8em; color: #94a3b8;'>ROI</div>
                                <div style='font-size: 1.1em; font-weight: bold; color: {roi_color};'>{roi:+.2f}%</div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
    
    # Summary chart
    st.divider()
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        fig_pie = px.pie(
            df_top,
            values='Market_Value',
            names='Ticker',
            title='Top 10 市值分佈',
            hole=0.4
        )
        fig_pie.update_layout(height=300, margin=dict(t=40, b=0, l=0, r=0))
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col_chart2:
        fig_bar = px.bar(
            df_top.sort_values('ROI (%)', ascending=True),
            x='ROI (%)',
            y='Ticker',
            orientation='h',
            title='Top 10 報酬率排行',
            color='ROI (%)',
            color_continuous_scale='RdYlGn'
        )
        fig_bar.update_layout(
            height=300,
            margin=dict(t=40, b=0, l=0, r=0),
            coloraxis_showscale=False
        )
        st.plotly_chart(fig_bar, use_container_width=True)


def render_monthly_returns_heatmap(history: list, c_symbol: str):
    """Monthly returns heatmap."""
    if not history or len(history) < 2:
        st.info("需要至少 2 個月的歷史數據才能顯示月度報酬熱力圖")
        return
    
    df = pd.DataFrame(history)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    
    y_col = "total_net_worth_usd" if "$" in c_symbol and "NT" not in c_symbol else "total_net_worth_twd"
    
    # Extract year and month
    df['year'] = df['date'].dt.year
    df['month'] = df['date'].dt.month
    
    # Calculate monthly returns
    df['return'] = df[y_col].pct_change() * 100
    
    # Group by year and month, taking the last value of each month
    monthly_data = df.groupby(['year', 'month']).agg({
        'return': 'sum',  # Sum of returns within the month
        y_col: 'last'
    }).reset_index()
    
    # Pivot for heatmap
    if len(monthly_data) > 0:
        pivot_data = monthly_data.pivot(index='year', columns='month', values='return')
        
        # Month names
        month_names = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
        pivot_data.columns = [month_names[m-1] for m in pivot_data.columns]
        
        # Create heatmap
        fig = go.Figure(data=go.Heatmap(
            z=pivot_data.values,
            x=pivot_data.columns,
            y=pivot_data.index,
            colorscale=[
                [0, '#d32f2f'],      # Deep red for negative
                [0.4, '#f44336'],    # Red
                [0.48, '#ffebee'],   # Light red
                [0.5, '#ffffff'],    # White for zero
                [0.52, '#e8f5e9'],   # Light green
                [0.6, '#4caf50'],    # Green
                [1, '#1b5e20']       # Deep green for positive
            ],
            text=pivot_data.values,
            texttemplate='%{text:.1f}%',
            textfont={"size": 10},
            colorbar=dict(title="報酬率 (%)"),
            hovertemplate='%{y}年 %{x}<br>報酬: %{z:.2f}%<extra></extra>'
        ))
        
        fig.update_layout(
            title='📊 月度報酬熱力圖',
            xaxis_title='月份',
            yaxis_title='年份',
            height=400,
            template='plotly_white'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Statistics
        col1, col2, col3, col4 = st.columns(4)
        avg_return = monthly_data['return'].mean()
        best_month = monthly_data.loc[monthly_data['return'].idxmax()]
        worst_month = monthly_data.loc[monthly_data['return'].idxmin()]
        positive_months = (monthly_data['return'] > 0).sum()
        total_months = len(monthly_data)
        win_rate = (positive_months / total_months * 100) if total_months > 0 else 0
        
        col1.metric("平均月報酬", f"{avg_return:.2f}%")
        col2.metric("最佳月份", f"{best_month['return']:.2f}%", f"{best_month['year']}/{best_month['month']}")
        col3.metric("最差月份", f"{worst_month['return']:.2f}%", f"{worst_month['year']}/{worst_month['month']}")
        col4.metric("勝率", f"{win_rate:.1f}%", f"{positive_months}/{total_months}")
    else:
        st.info("歷史數據不足，無法生成熱力圖")


def render_advanced_charts_section(df_all: pd.DataFrame, total_val: float, c_symbol: str, exchange_rate: float):
    """Render advanced charts section with chart selector."""
    st.markdown("## 📊 進階圖表分析")
    st.caption("深入分析您的投資組合績效與配置")
    
    # Chart selector
    chart_options = [
        "🚀 淨資產成長趨勢（增強版）",
        "🕸️ 資產配置雷達圖",
        "🏆 Top 10 持倉績效",
        "📊 月度報酬熱力圖"
    ]
    
    selected_chart = st.selectbox(
        "選擇要查看的圖表",
        chart_options,
        index=0,  # Default to enhanced net worth
        key="advanced_chart_selector"
    )
    
    st.divider()
    
    # Render selected chart
    history = st.session_state.get("history_data", [])
    
    if selected_chart == chart_options[0]:
        render_enhanced_networth_chart(history, c_symbol)
    elif selected_chart == chart_options[1]:
        render_allocation_radar_chart(df_all, total_val)
    elif selected_chart == chart_options[2]:
        render_top10_holdings_dashboard(df_all, c_symbol)
    elif selected_chart == chart_options[3]:
        render_monthly_returns_heatmap(history, c_symbol)