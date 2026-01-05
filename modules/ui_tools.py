"""
Tools UI Module.

This module provides utility tools including:
- Fund deployment calculator
- ATR risk analysis
- SL/TP calculators
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from modules.data_loader import save_all_data
from modules.risk_management import suggest_sl_tp_for_holding, calculate_atr, suggest_sl_tp_for_entry
from modules.market_service import fetch_historical_data
from modules.logger import get_logger
from config import get_config

config = get_config()
logger = get_logger(__name__)


# ===========================
# Fund Deployment Calculator
# ===========================

def calculate_base_suggestions(df_market_data, total_val, new_fund):
    """計算系統建議的原始分配"""
    if not df_market_data.empty:
        current_alloc = df_market_data.groupby("Type")["Market_Value"].sum()
    else:
        current_alloc = pd.Series(dtype=float)

    targets = st.session_state.allocation_targets
    all_types = list(targets.keys())

    final_total_val = total_val + new_fund
    suggestions = []

    for cat in all_types:
        target_pct =targets.get(cat, 0.0) / 100.0
        current_val = current_alloc.get(cat, 0.0)
        ideal_val = final_total_val * target_pct
        gap = ideal_val - current_val
        suggestions.append({"Type": cat, "Gap": gap if gap > 0 else 0})

    df_sug = pd.DataFrame(suggestions)
    total_gap = df_sug["Gap"].sum()

    if total_gap > new_fund and total_gap > 0:
        df_sug["Suggested"] = df_sug.apply(
            lambda x: (x["Gap"] / total_gap * new_fund), axis=1
        )
    else:
        remaining = new_fund - total_gap
        df_sug["Suggested"] = df_sug.apply(
            lambda x: x["Gap"] + (remaining * (targets.get(x["Type"], 0) / 100)), axis=1
        )

    return df_sug.set_index("Type")["Suggested"].to_dict()


def render_fund_calculator(df_market_data, c_symbol, total_val):
    """Render fund deployment calculator tool."""
    st.subheader("💰 資金投入與部署計劃")
    st.caption("規劃新資金的分配並建立交易清單")

    # Initialize session state
    if "draft_actions" not in st.session_state:
        st.session_state.draft_actions = []

    # Step 1: Planning
    with st.expander(
        "1️⃣ 規劃資金分配", expanded=not bool(st.session_state.draft_actions)
    ):
        col_in1, col_in2 = st.columns([1, 2])
        new_fund = col_in1.number_input(
            f"預計投入金額 ({c_symbol})",
            min_value=0.0,
            value=10000.0,
            step=1000.0,
            key="calc_fund_input",
        )

        # Calculate suggestions
        if (
            "calc_base_suggestions" not in st.session_state
            or new_fund != st.session_state.get("last_calc_fund", 0)
        ):
            base_sug = calculate_base_suggestions(df_market_data, total_val, new_fund)
            st.session_state.calc_base_suggestions = base_sug
            st.session_state.calc_manual_adjust = base_sug.copy()
            st.session_state.last_calc_fund = new_fund

        current_plan = st.session_state.calc_manual_adjust

        c_adjust, c_charts = st.columns([1, 1.2])

        with c_adjust:
            st.markdown("#### 🛠️ 調整預算")
            if st.button("↺ 重置建議"):
                reset_data = st.session_state.calc_base_suggestions.copy()
                st.session_state.calc_manual_adjust = reset_data
                for cat in reset_data.keys():
                    key = f"man_adj_{cat}"
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

            total_manual = 0
            for cat in current_plan.keys():
                key = f"man_adj_{cat}"
                default_val = float(current_plan[cat])
                new_amt = st.number_input(
                    f"{cat}", 0.0, value=default_val, step=1000.0, key=key
                )
                current_plan[cat] = new_amt
                total_manual += new_amt

            diff = total_manual - new_fund
            if abs(diff) > 1:
                st.caption(f"差額: {c_symbol}{diff:+,.0f}")
            else:
                st.success(f"已分配: {c_symbol}{total_manual:,.0f}")

        with c_charts:
            labels = list(current_plan.keys())
            vals = list(current_plan.values())
            
            fig1 = go.Figure(
                data=[go.Pie(labels=labels, values=vals, hole=0.4, title="本次配置")]
            )
            fig1.update_layout(
                margin=dict(t=30, b=0, l=0, r=0), height=180, showlegend=False
            )
            st.plotly_chart(fig1, use_container_width=True)

            # Expected total
            if not df_market_data.empty:
                cur_vals = (
                    df_market_data.groupby("Type")["Market_Value"].sum().to_dict()
                )
            else:
                cur_vals = {}
            final_vals = {
                cat: cur_vals.get(cat, 0) + current_plan.get(cat, 0)
                for cat in set(list(cur_vals.keys()) + labels)
            }
            fig2 = go.Figure(
                data=[
                    go.Pie(
                        labels=list(final_vals.keys()),
                        values=list(final_vals.values()),
                        hole=0.4,
                        title="預期總覽",
                    )
                ]
            )
            fig2.update_layout(
                margin=dict(t=30, b=0, l=0, r=0), height=180, showlegend=True
            )
            st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # Step 2: Create deployment list
    st.markdown("### 2️⃣ 建立交易清單")
    st.caption("根據上方的預算，將資金分配到具體的資產上")

    active_cats = [c for c, v in current_plan.items() if v > 0]
    if not active_cats:
        st.info("請先在上方規劃預算。")
    else:
        sel_cat = st.selectbox("選擇要配置的類別", active_cats)
        budget = current_plan.get(sel_cat, 0)

        planned_in_cat = sum(
            [d["Total"] for d in st.session_state.draft_actions if d["Type"] == sel_cat]
        )
        remaining = budget - planned_in_cat

        st.markdown(
            f"**{sel_cat}** 預算: `{c_symbol}{budget:,.0f}` | 已規劃: `{c_symbol}{planned_in_cat:,.0f}` | 剩餘: :blue[**{c_symbol}{remaining:,.0f}**]"
        )

        # SL/TP Calculator
        with st.expander("🎯 SL/TP 計算器 (風控輔助工具)", expanded=False):
            st.caption("根據 ATR 和最大可接受損失計算建議的停損、停利和購買數量")
            
            col_calc1, col_calc2, col_calc3 = st.columns(3)
            
            calc_ticker = col_calc1.text_input(
                "代號",
                placeholder="如 AAPL",
                key="sltp_calc_ticker"
            ).upper()
            
            calc_entry_price = col_calc2.number_input(
                "預計入場價格",
                min_value=0.0,
                value=100.0,
                step=1.0,
                key="sltp_calc_entry"
            )
            
            calc_max_loss = col_calc3.number_input(
                f"最大可接受損失 ({c_symbol})",
                min_value=0.0,
                value=1000.0,
                step=100.0,
                key="sltp_calc_max_loss"
            )
            
            col_param1, col_param2 = st.columns(2)
            calc_atr_mult = col_param1.slider(
                "ATR 倍數",
                min_value=1.0,
                max_value=5.0,
                value=2.0,
                step=0.5,
                key="sltp_calc_atr_mult"
            )
            
            calc_r_ratio = col_param2.slider(
                "R-Ratio",
                min_value=1.0,
                max_value=5.0,
                value=2.0,
                step=0.5,
                key="sltp_calc_r_ratio"
            )
            
            if st.button("🔍 計算建議", key="btn_calc_sltp", type="primary"):
                if not calc_ticker:
                    st.error("請輸入代號")
                else:
                    with st.spinner(f"正在計算 {calc_ticker} 的 ATR..."):
                        atr_value = calculate_atr(calc_ticker)
                        
                        if atr_value:
                            result = suggest_sl_tp_for_entry(
                                entry_price=calc_entry_price,
                                atr_value=atr_value,
                                max_loss_amount=calc_max_loss,
                                atr_multiplier=calc_atr_mult,
                                r_ratio=calc_r_ratio
                            )
                            
                            st.session_state["sltp_calc_result"] = result
                            st.session_state["sltp_calc_ticker"] = calc_ticker
                            st.success("✅ 計算完成！")
                            st.rerun()
                        else:
                            st.error("❌ 無法獲取 ATR 數據，請檢查代號是否正確")
            
            # Display results
            if "sltp_calc_result" in st.session_state:
                result = st.session_state["sltp_calc_result"]
                ticker = st.session_state.get("sltp_calc_ticker", "")
                
                st.divider()
                st.markdown("### 📊 計算結果")
                
                col_r1, col_r2, col_r3, col_r4 = st.columns(4)
                col_r1.metric("1R 距離", f"{result['one_r_distance']:.2f}")
                col_r2.metric("🔴 停損價", f"{result['sl_price']:.2f}")
                col_r3.metric("🟢 停利價", f"{result['tp_price']:.2f}")
                col_r4.metric("📦 建議數量", f"{result['max_qty']:.2f}")
                
                st.info(f"""
                **風險分析:**
                - 風險金額: {c_symbol}{result['risk_amount']:,.2f}
                - 潛在獲利: {c_symbol}{result['reward_amount']:,.2f}
                - 風險回報比: 1:{calc_r_ratio}
                """)
                
                if st.button("✅ 使用建議數量", key="btn_use_sltp_qty"):
                    st.session_state["deploy_qty_override"] = result['max_qty']
                    st.session_state["deploy_ticker_override"] = ticker
                    st.session_state["deploy_price_override"] = calc_entry_price
                    st.success(f"已設定數量為 {result['max_qty']:.2f}，請在下方確認並加入清單")
                    st.rerun()

        # Deployment form
        with st.container(border=True):
            col_act1, col_act2, col_act3, col_act4 = st.columns([1.5, 1, 1, 1])

            existing_assets = [
                p.get("symbol") or p.get("Ticker") for p in st.session_state.portfolio 
                if (p.get("asset_class") or p.get("Type")) == sel_cat
            ]
            asset_opt = col_act1.selectbox(
                "選擇資產", ["➕ 新增資產..."] + existing_assets, key="deploy_asset_sel"
            )

            target_ticker = ""
            if asset_opt == "➕ 新增資產...":
                default_ticker = st.session_state.get("deploy_ticker_override", "")
                target_ticker = col_act1.text_input(
                    "輸入新代號", 
                    value=default_ticker,
                    placeholder="如 AAPL", 
                    key="deploy_new_ticker"
                ).upper()
            else:
                target_ticker = asset_opt

            ref_price = st.session_state.get("deploy_price_override", 100.0)
            if asset_opt != "➕ 新增資產...":
                ref_item = next(
                    (p for p in st.session_state.portfolio if (p.get("symbol") or p.get("Ticker")) == asset_opt),
                    None,
                )
                if ref_item:
                    ref_price = float(ref_item.get("avg_cost") or ref_item.get("Avg_Cost", 100.0))

            d_price = col_act2.number_input(
                "單價", 0.0, value=float(ref_price), key="deploy_price"
            )
            
            default_qty = st.session_state.get("deploy_qty_override", 1.0)
            d_qty = col_act3.number_input("數量", 0.0, value=float(default_qty), key="deploy_qty")

            d_total = d_price * d_qty
            col_act4.markdown(f"總額: **{d_total:,.0f}**")

            if col_act4.button("加入清單", type="primary", disabled=d_total <= 0):
                if not target_ticker:
                    st.error("請輸入代號")
                else:
                    st.session_state.draft_actions.append(
                        {
                            "Type": sel_cat,
                            "Ticker": target_ticker,
                            "Price": d_price,
                            "Qty": d_qty,
                            "Total": d_total,
                            "Is_New": asset_opt == "➕ 新增資產...",
                        }
                    )
                    st.success(f"已加入 {target_ticker}")
                    st.rerun()

    # Step 3: Execute
    if st.session_state.draft_actions:
        st.divider()
        st.markdown("### 3️⃣ 確認並執行")

        draft_df = pd.DataFrame(st.session_state.draft_actions)
        st.dataframe(draft_df, use_container_width=True, key="draft_actions_table")

        total_planned = draft_df["Total"].sum()
        st.markdown(f"#### 總計畫投入金額: :green[{c_symbol}{total_planned:,.0f}]")

        c_sub1, c_sub2 = st.columns([1, 4])
        if c_sub1.button("🗑️ 清空清單"):
            st.session_state.draft_actions = []
            st.rerun()

        if c_sub2.button("🚀 確認送出 (寫入投資組合)", type="primary"):
            for action in st.session_state.draft_actions:
                ticker = action["Ticker"]
                existing_idx = next(
                    (
                        i
                        for i, p in enumerate(st.session_state.portfolio)
                        if (p.get("symbol") or p.get("Ticker")) == ticker
                    ),
                    -1,
                )

                if existing_idx >= 0:
                    # Update existing
                    item = st.session_state.portfolio[existing_idx]
                    current_qty = item.get("quantity") if item.get("quantity") is not None else item.get("Quantity", 0.0)
                    current_avg = item.get("avg_cost") if item.get("avg_cost") is not None else item.get("Avg_Cost", 0.0)
                    
                    old_cost = current_qty * current_avg
                    new_qty = current_qty + action["Qty"]
                    new_avg = (old_cost + action["Total"]) / new_qty if new_qty else 0
                    
                    st.session_state.portfolio[existing_idx]["quantity"] = new_qty
                    st.session_state.portfolio[existing_idx]["avg_cost"] = new_avg
                    if "Quantity" in item: st.session_state.portfolio[existing_idx]["Quantity"] = new_qty
                    if "Avg_Cost" in item: st.session_state.portfolio[existing_idx]["Avg_Cost"] = new_avg
                else:
                    # Add new
                    curr = "TWD" if ".TW" in ticker else "USD"
                    new_id = f"ast_{datetime.now().strftime('%Y%m%d%H%M%S')}_{ticker}"
                    st.session_state.portfolio.append(
                        {
                            "asset_id": new_id,
                            "asset_class": action["Type"],
                            "symbol": ticker,
                            "quantity": action["Qty"],
                            "avg_cost": action["Price"],
                            "currency": curr,
                            "manual_price": 0.0,
                            "last_update": "N/A",
                            "account_id": "default_main",
                        }
                    )

            save_all_data(
                st.session_state.accounts, 
                st.session_state.portfolio, 
                st.session_state.allocation_targets, 
                st.session_state.history_data,
                st.session_state.get("loan_plans", [])
            )
            st.session_state["force_refresh_market_data"] = True
            st.session_state.draft_actions = []
            st.success("交易已成功執行！請至資產管理頁面查看。")
            st.balloons()
    else:
        st.info("尚未加入任何交易計畫。")


# ===========================
# ATR Risk Analysis Tool
# ===========================

@st.cache_data(ttl=3600)
def get_cached_historical_data(ticker: str, period: str = '3mo') -> pd.DataFrame:
    """Fetch and cache historical data for 1 hour."""
    logger.info(f"Fetching historical data for {ticker}")
    return fetch_historical_data(ticker, period=period, interval='1d')


@st.cache_data(ttl=3600)
def get_cached_atr(ticker: str, period: int = 14):
    """Calculate and cache ATR for 1 hour."""
    logger.info(f"Calculating ATR for {ticker}")
    return calculate_atr(ticker, period=period)


def create_stock_chart(hist_data: pd.DataFrame, ticker: str, sl_price=None, 
                       tp_price=None, avg_cost=None):
    """Create interactive stock chart with SL/TP lines."""
    fig = go.Figure()
    
    # Candlestick
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
    
    # Volume
    fig.add_trace(go.Bar(
        x=hist_data.index,
        y=hist_data['Volume'],
        name='Volume',
        yaxis='y2',
        marker_color='rgba(128, 128, 128, 0.3)'
    ))
    
    # Lines
    if avg_cost:
        fig.add_hline(
            y=avg_cost,
            line_dash="dash",
            line_color="blue",
            annotation_text=f"平均成本: ${avg_cost:.2f}",
            annotation_position="right"
        )
    
    if sl_price:
        fig.add_hline(
            y=sl_price,
            line_dash="dot",
            line_color="red",
            annotation_text=f"停損: ${sl_price:.2f}",
            annotation_position="right"
        )
    
    if tp_price:
        fig.add_hline(
            y=tp_price,
            line_dash="dot",
            line_color="green",
            annotation_text=f"停利: ${tp_price:.2f}",
            annotation_position="right"
        )
    
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
    """Render ATR risk analysis tool."""
    st.subheader("📈 ATR 風控分析")
    st.caption("選擇持倉進行 ATR 風控分析，查看建議的停損停利線與股價走勢圖")
    
    if not portfolio:
        st.info("目前沒有持倉。請先在「資產管理」頁面新增資產。")
        return
    
    # Selection
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
    
    selected_ticker = selected_option.split(" (")[0]
    selected_asset = next((a for a in portfolio if (a.get("symbol") or a.get("Ticker")) == selected_ticker), None)
    
    if not selected_asset:
        st.error("找不到選擇的資產")
        return
    
    # Display info
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
    
    # Parameters
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
    
    # Calculate
    if st.button("🔍 執行分析", type="primary", use_container_width=True):
        with st.spinner(f"正在分析 {selected_ticker}..."):
            man_price = selected_asset.get("manual_price")
            if man_price is None: man_price = selected_asset.get("Manual_Price", 0.0)
            
            current_price = man_price if man_price > 0 else a_cost
            if current_price == 0:
                current_price = a_cost
            
            result = suggest_sl_tp_for_holding(
                ticker=selected_ticker,
                avg_cost=a_cost,
                current_price=current_price,
                atr_multiplier=atr_multiplier,
                r_ratio=r_ratio,
                atr_period=atr_period
            )
            
            if result:
                st.session_state['risk_analysis_result'] = result
                st.session_state['risk_analysis_ticker'] = selected_ticker
                st.session_state['risk_analysis_asset'] = selected_asset
                st.success("✅ 分析完成！")
                st.rerun()
            else:
                st.error("❌ 無法計算 ATR，可能是數據不足或代號錯誤")
    
    # Display results
    if 'risk_analysis_result' in st.session_state and \
       st.session_state.get('risk_analysis_ticker') == selected_ticker:
        
        result = st.session_state['risk_analysis_result']
        asset = st.session_state['risk_analysis_asset']
        
        st.divider()
        st.subheader("📊 分析結果")
        
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("ATR 值", f"{result['atr_value']:.4f}", help="平均真實波動區間")
        col_m2.metric("1R 距離", f"{result['one_r_distance']:.2f}", help="單位風險距離")
        col_m3.metric("當前風險", f"{c_symbol}{result['current_risk']:.2f}")
        col_m4.metric("潛在獲利", f"{c_symbol}{result['current_reward']:.2f}")
        
        st.divider()
        
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
        
        # Stock chart
        st.subheader("📈 股價走勢圖")
        
        with st.spinner("載入股價圖表..."):
            hist_data = get_cached_historical_data(selected_ticker, period='3mo')
            
            if not hist_data.empty:
                st.caption("💾 圖表數據已快取 1 小時")
                
                fig = create_stock_chart(
                    hist_data,
                    selected_ticker,
                    sl_price=result['sl_price'],
                    tp_price=result['tp_price'],
                    avg_cost=a_cost
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Statistics
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


# ===========================
# Main Tool Page Entry
# ===========================

def render_tools(df_market_data, c_symbol, total_val, portfolio):
    """
    Main entry point for Tools & Utilities page.
    
    Args:
        df_market_data: Market data DataFrame
        c_symbol: Currency symbol
        total_val: Total portfolio value
        portfolio: Portfolio list
    """
    st.title("🛠️ 輔助工具")
    st.caption("資金規劃、風控分析等輔助工具")
    
    # Organize tools in tabs
    tool_tab1, tool_tab2 = st.tabs(["💰 資金投入計劃", "📈 ATR 風控分析"])
    
    with tool_tab1:
        render_fund_calculator(df_market_data, c_symbol, total_val)
    
    with tool_tab2:
        render_risk_analysis(portfolio, c_symbol)
