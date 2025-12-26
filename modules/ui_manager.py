import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from modules.data_loader import save_all_data
from modules.market_service import search_yahoo_ticker, fetch_single_price
from models import Account
from config import get_config

config = get_config()

# ===========================
# 輔助函式與 CSS
# ===========================


def check_is_outdated(last_update_str):
    if not last_update_str or last_update_str == "N/A":
        return True
    try:
        last_update_dt = datetime.strptime(last_update_str, "%Y-%m-%d %H:%M")
        return datetime.now() - last_update_dt > timedelta(days=1)
    except:
        return True


def inject_custom_css():
    st.markdown(
        """
    <style>
    .fab-container { position: fixed; bottom: 40px; right: 40px; z-index: 9999; }
    .fab-container button {
        background-color: #FF4B4B; color: white; border-radius: 50%;
        width: 60px; height: 60px; font-size: 24px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.3); border: none; transition: transform 0.2s;
    }
    .fab-container button:hover { transform: scale(1.1); background-color: #FF2B2B; }
    .highlight-box { background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 10px; }
    </style>
    """,
        unsafe_allow_html=True,
    )


# ===========================
# 邏輯核心：再平衡計算
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
        target_pct = targets.get(cat, 0.0) / 100.0
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


# ===========================
# 彈窗與操作邏輯
# ===========================


@st.dialog("⚙️ 資產管理與交易")
@st.dialog("⚙️ 資產管理與交易")
def asset_action_dialog(index, asset):
    # Map legacy keys if present (for safe migration)
    ticker = asset.get("symbol") or asset.get("Ticker")
    atype = asset.get("asset_class") or asset.get("Type")
    curr = asset.get("currency") or asset.get("Currency")
    avg_cost = asset.get("avg_cost")
    if avg_cost is None: avg_cost = asset.get("Avg_Cost", 0.0)
    qty = asset.get("quantity")
    if qty is None: qty = asset.get("Quantity", 0.0)
    
    st.header(f"管理：{ticker}")
    st.caption(f"類別: {atype} | 幣別: {curr}")

    # We use tabs for different actions
    tab_buy, tab_sell, tab_edit, tab_move, tab_risk, tab_del = st.tabs(
        ["➕ 加倉 (Buy)", "➖ 減倉 (Sell)", "✏️ 修正 (Edit)", "💸 轉帳 (Move)", "📈 風控 (Risk)", "🗑️ 刪除 (Delete)"]
    )

    with tab_buy:
        st.markdown("#### 增加持倉")
        c1, c2 = st.columns(2)
        add_qty = c1.number_input("加倉數量", min_value=0.0, value=0.0, step=0.1, key=f"bq_{index}")
        add_price = c2.number_input(
            f"成交單價 ({curr})",
            min_value=0.0,
            value=float(avg_cost),
            key=f"bp_{index}",
        )

        st.info(f"預估投入金額: {curr} {add_qty * add_price:,.2f}")

        if st.button("確認加倉", key=f"btn_buy_{index}", type="primary", use_container_width=True):
            if add_qty > 0:
                old_cost = qty * avg_cost
                new_qty = qty + add_qty
                new_avg = (
                    (old_cost + (add_qty * add_price)) / new_qty if new_qty else 0
                )
                asset["avg_cost"] = new_avg
                asset["quantity"] = new_qty
                
                # Update legacy keys if they exist
                if "Avg_Cost" in asset: asset["Avg_Cost"] = new_avg
                if "Quantity" in asset: asset["Quantity"] = new_qty
                
                save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data)
                st.session_state["force_refresh_market_data"] = True
                st.success("加倉成功！")
                st.rerun()
            else:
                st.error("數量必須大於 0")

    with tab_sell:
        st.markdown("#### 減少持倉")
        sell_qty = st.number_input(
            "賣出數量",
            min_value=0.0,
            max_value=float(qty),
            value=0.0,
            step=0.1,
            key=f"sq_{index}"
        )

        # Calculate estimated realized P/L if we knew current price (omitted for simplicity or need to pass it in)

        if st.button("確認減倉", key=f"btn_sell_{index}", type="primary", use_container_width=True):
            if sell_qty > 0:
                asset["quantity"] = qty - sell_qty
                if asset["quantity"] < 0: asset["quantity"] = 0 # Safety
                
                if "Quantity" in asset: asset["Quantity"] = asset["quantity"]
                
                save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data)
                st.session_state["force_refresh_market_data"] = True
                st.success("減倉成功！")
                st.rerun()
            else:
                st.error("數量必須大於 0")

    with tab_edit:
        st.markdown("#### 修正數據 (不影響損益計算邏輯，僅修改記錄)")
        c1, c2 = st.columns(2)
        fq = c1.number_input(
            "持有數量", min_value=0.0, value=float(qty), key=f"fq_{index}"
        )
        fc = c2.number_input(
            "平均成本", min_value=0.0, value=float(avg_cost), key=f"fc_{index}"
        )

        # Account modification
        accounts = st.session_state.get("accounts", [])
        acc_options = {acc["name"]: str(acc.get("account_id") or acc.get("id")) for acc in accounts} if accounts else {"主要帳戶": "default_main"}
        # Reverse map for default index
        curr_acc_id = asset.get("account_id") or asset.get("Account_ID", "default_main")

        # Find index of current account in options keys
        # This is a bit tricky, simpler to just list names and find match
        acc_names = list(acc_options.keys())
        default_acc_index = 0
        for i, name in enumerate(acc_names):
            if acc_options[name] == curr_acc_id:
                default_acc_index = i
                break

        sel_acc_name = st.selectbox("所屬帳戶", acc_names, index=default_acc_index, key=f"acc_edit_{index}")

        if st.button("保存修正", key=f"btn_fix_{index}", use_container_width=True):
            asset["quantity"] = fq
            asset["avg_cost"] = fc
            asset["account_id"] = acc_options[sel_acc_name]
            
            if "Quantity" in asset: asset["Quantity"] = fq
            if "Avg_Cost" in asset: asset["Avg_Cost"] = fc
            if "Account_ID" in asset: asset["Account_ID"] = asset["account_id"]
            
            save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data)
            st.session_state["force_refresh_market_data"] = True
            st.success("數據已更新")
            st.rerun()

    with tab_move:
        st.markdown("#### 無損移轉 (不影響損益)")
        st.caption("將資產移動至另一個帳戶，例如：從主要帳戶移動至美股帳戶。")
        
        # Account selection for transfer
        accounts = st.session_state.get("accounts", [])
        acc_options = {acc["name"]: str(acc.get("account_id") or acc.get("id")) for acc in accounts} if accounts else {"主要帳戶": "default_main"}
        curr_acc_id = asset.get("account_id") or asset.get("Account_ID", "default_main")
        
        # Filter out current account
        target_acc_names = [name for name, aid in acc_options.items() if aid != curr_acc_id]
        
        if not target_acc_names:
            st.info("沒有其他帳戶可供移轉。請先新增帳戶。")
        else:
            target_name = st.selectbox("移轉至目標帳戶", target_acc_names, key=f"move_acc_{index}")
            
            if st.button("確認移轉", key=f"btn_move_{index}", type="primary", use_container_width=True):
                target_id = acc_options[target_name]
                asset["account_id"] = target_id
                if "Account_ID" in asset: asset["Account_ID"] = target_id
                
                save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data)
                st.session_state["force_refresh_market_data"] = True
                st.success(f"已移轉至 {target_name}")
                st.rerun()

    with tab_risk:
        st.markdown("### 🎯 ATR 風控建議")
        st.caption(f"根據 ATR (平均真實波動區間) 計算停損停利建議")
        
        # Display current position info
        col_info1, col_info2 = st.columns(2)
        col_info1.metric("代號", ticker)
        col_info2.metric("平均成本", f"{asset.get('currency', 'USD')} {avg_cost:.2f}")
        
        # Get current price from market data if available
        current_price = asset.get("manual_price")
        if current_price is None: current_price = asset.get("Manual_Price", 0.0)
        
        if current_price == 0:
            current_price = avg_cost
        
        col_info1.metric("當前價格", f"{asset.get('currency', 'USD')} {current_price:.2f}")
        col_info2.metric("持有數量", f"{qty:.2f}")
        
        st.divider()
        
        # Parameter inputs
        col_param1, col_param2 = st.columns(2)
        atr_multiplier = col_param1.slider(
            "ATR 倍數",
            min_value=1.0,
            max_value=5.0,
            value=2.0,
            step=0.5,
            key=f"atr_mult_{index}",
            help="用於計算停損距離的 ATR 倍數"
        )
        r_ratio = col_param2.slider(
            "R-Ratio (風險回報比)",
            min_value=1.0,
            max_value=5.0,
            value=2.0,
            step=0.5,
            key=f"r_ratio_{index}",
            help="停利目標相對於停損的倍數"
        )
        
        # Calculate button
        if st.button("🔍 計算建議線", key=f"calc_risk_{index}", type="primary"):
            from modules.risk_management import suggest_sl_tp_for_holding
            
            with st.spinner(f"正在計算 {asset['Ticker']} 的風控建議..."):
                result = suggest_sl_tp_for_holding(
                    ticker=ticker,
                    avg_cost=avg_cost,
                    current_price=current_price,
                    atr_multiplier=atr_multiplier,
                    r_ratio=r_ratio
                )
                
                if result:
                    st.session_state[f"risk_calc_{index}"] = result
                    st.success("✅ 計算完成！")
                    st.rerun()
                else:
                    st.error("❌ 無法計算 ATR，可能是數據不足或代號錯誤")
        
        # Display results if available
        if f"risk_calc_{index}" in st.session_state:
            result = st.session_state[f"risk_calc_{index}"]
            
            st.divider()
            st.markdown("### 📊 計算結果")
            
            # Display metrics
            col_r1, col_r2, col_r3 = st.columns(3)
            col_r1.metric(
                "ATR 值",
                f"{result['atr_value']:.4f}",
                help="當前的平均真實波動區間"
            )
            col_r2.metric(
                "1R 距離",
                f"{result['one_r_distance']:.2f}",
                help="單位風險距離 (ATR × 倍數)"
            )
            col_r3.metric(
                "未實現損益",
                f"{result['unrealized_pl_pct']:.2f}%",
                delta=f"{result['unrealized_pl_pct']:.2f}%"
            )
            
            st.divider()
            
            # SL/TP prices
            col_sl, col_tp = st.columns(2)
            col_sl.markdown(f"""
            <div style='background-color: #ffebee; padding: 15px; border-radius: 10px; border-left: 4px solid #f44336;'>
                <h4 style='margin: 0; color: #c62828;'>🔴 建議停損 (SL)</h4>
                <h2 style='margin: 5px 0; color: #c62828;'>{asset['Currency']} {result['sl_price']:.2f}</h2>
                <p style='margin: 0; font-size: 12px; color: #666;'>風險: {result['current_risk']:.2f}</p>
            </div>
            """, unsafe_allow_html=True)
            
            col_tp.markdown(f"""
            <div style='background-color: #e8f5e9; padding: 15px; border-radius: 10px; border-left: 4px solid #4caf50;'>
                <h4 style='margin: 0; color: #2e7d32;'>🟢 建議停利 (TP)</h4>
                <h2 style='margin: 5px 0; color: #2e7d32;'>{asset['Currency']} {result['tp_price']:.2f}</h2>
                <p style='margin: 0; font-size: 12px; color: #666;'>目標: {result['current_reward']:.2f}</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.divider()
            
            # Save button
            if st.button("💾 應用建議並儲存", key=f"save_risk_{index}", type="primary"):
                asset["suggested_sl"] = result['sl_price']
                asset["suggested_tp"] = result['tp_price']
                if "Suggested_SL" in asset: asset["Suggested_SL"] = result['sl_price']
                if "Suggested_TP" in asset: asset["Suggested_TP"] = result['tp_price']
                
                save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data)
                st.success(f"✅ 已儲存 {ticker} 的停損停利建議！")
                st.rerun()

    with tab_del:
        if st.button("❌ 確認刪除", key=f"btn_del_{index}", type="primary"):
            st.session_state.portfolio.pop(index)
            save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data)
            st.session_state["force_refresh_market_data"] = True
            st.rerun()



            if ticker:
                final_curr = curr
                if final_curr == "Auto":
                    final_curr = "TWD" if ".TW" in ticker else "USD"
                
                # Default account
                acc_id = "default_main"
                if "accounts" in st.session_state and st.session_state.accounts:
                     # Logic to select account?
                     # We should have added a selector in the dialog.
                     # Let's add it below.
                     pass 

@st.dialog("➕ 新增資產")
def add_asset_dialog():
    st.caption("搜尋代號 (如: TSLA, 2330)")
    c_s, c_r = st.columns([2, 3])
    q = c_s.text_input("搜尋", placeholder="輸入代號...")
    sel = c_r.selectbox("結果", search_yahoo_ticker(q) if q else [])
    st.markdown("---")
    
    # Pre-fetch accounts
    accounts = st.session_state.get("accounts", [])
    acc_options = {acc["name"]: str(acc.get("account_id") or acc.get("id")) for acc in accounts} if accounts else {"主要帳戶": "default_main"}
    
    c1, c2 = st.columns(2)
    auto_t = sel.split(" | ")[0] if sel else ""
    with c1:
        ticker = st.text_input("代號", value=auto_t).upper()
        atype = st.selectbox("類別", config.ui.asset_types) # Use config types
        sel_acc_name = st.selectbox("帳戶", list(acc_options.keys()))
        sel_acc_id = acc_options[sel_acc_name]
        
    with c2:
        qty = st.number_input("數量", min_value=0.0, value=1.0, step=1.0, format="%.0f")
        curr = st.selectbox("幣別", ["USD", "TWD"], index=0)
        cost = st.number_input("成本", min_value=0.0, value=100.0, step=0.01)

    if st.button("確認新增", type="primary", use_container_width=True):
        if ticker:
            # Generate new asset_id
            new_id = f"ast_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            st.session_state.portfolio.append(
                {
                    "asset_id": new_id,
                    "asset_class": atype,
                    "symbol": ticker,
                    "quantity": qty,
                    "avg_cost": cost,
                    "currency": curr,
                    "manual_price": 0.0,
                    "last_update": "N/A",
                    "account_id": sel_acc_id,
                }
            )
            save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data)
            st.session_state["force_refresh_market_data"] = True
            st.success(f"已新增 {ticker}")
            st.rerun()


# ===========================
# 1. 優化後的投資配置設定
# ===========================
def render_allocation_section():
    st.subheader("🎯 投資配置目標設定")
    current_types = set([p.get("asset_class") or p.get("Type") for p in st.session_state.portfolio])
    all_types = list(current_types.union({"美股", "台股", "虛擬貨幣", "稀有金屬"}))
    new_targets = {}
    total_pct = 0.0

    cols = st.columns(4)
    for i, cat in enumerate(all_types):
        col = cols[i % 4]
        cur_val = st.session_state.allocation_targets.get(cat, 0.0)
        val = col.number_input(
            f"{cat} (%)", 0.0, 100.0, float(cur_val), step=5.0, key=f"alloc_{cat}"
        )
        new_targets[cat] = val
        total_pct += val

    st.divider()

    # --- 進度條與數值顯示 ---
    c_bar, c_info = st.columns([4, 1])
    with c_bar:
        # 超過 100% 用紅色，否則用預設藍色
        bar_color = "red" if total_pct > 100 else "blue"
        # Streamlit progress bar color 只能透過 theme 設定，這裡用 value 限制視覺
        st.progress(min(total_pct / 100, 1.0))

    with c_info:
        if total_pct > 100:
            st.markdown(f"🚫 :red[**{total_pct:.1f}%**]")
        elif total_pct == 100:
            st.markdown(f"✅ :green[**{total_pct:.1f}%**]")
        else:
            st.markdown(f"⚠️ **{total_pct:.1f}%**")

    # 儲存按鈕邏輯
    if total_pct > 100:
        st.error("總配置比例超過 100%，請調整後再儲存。")
        st.button("💾 儲存配置設定", disabled=True)
    else:
        if st.button("💾 儲存配置設定"):
            st.session_state.allocation_targets = new_targets
            save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data)
            st.success("設定已儲存")


# ===========================
# 3. 資金投入試算與執行 (Smart Deployment)
# ===========================
def render_calculator_section(df_market_data, c_symbol, total_val):
    st.subheader("💰 資金投入與部署")

    # 初始化 Session State
    if "draft_actions" not in st.session_state:
        st.session_state.draft_actions = []

    # --- Step 1: 試算與規劃 ---
    with st.expander(
        "1️⃣ 規劃資金分配 (Step 1)", expanded=not bool(st.session_state.draft_actions)
    ):
        col_in1, col_in2 = st.columns([1, 2])
        new_fund = col_in1.number_input(
            f"預計投入金額 ({c_symbol})",
            min_value=0.0,
            value=10000.0,
            step=1000.0,
            key="calc_fund_input",
        )

        # 初始化建議
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
                # Clear the widget keys so they can be recreated with new values
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
            # 圖 1: 本次分配
            fig1 = go.Figure(
                data=[go.Pie(labels=labels, values=vals, hole=0.4, title="本次配置")]
            )
            fig1.update_layout(
                margin=dict(t=30, b=0, l=0, r=0), height=180, showlegend=False
            )
            st.plotly_chart(fig1, use_container_width=True)

            # 圖 2: 預期總資產
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

    # --- Step 2: 建立部署清單 ---
    st.markdown("### 2️⃣ 建立交易清單 (Step 2)")
    st.caption("請根據上方的預算，將資金分配到具體的資產上。")

    # 選擇要操作的類別 (只顯示有預算的)
    active_cats = [c for c, v in current_plan.items() if v > 0]
    if not active_cats:
        st.info("請先在上方規劃預算。")
    else:
        sel_cat = st.selectbox("選擇要配置的類別", active_cats)
        budget = current_plan.get(sel_cat, 0)

        # 計算該類別已規劃多少
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
                    from modules.risk_management import calculate_atr, suggest_sl_tp_for_entry
                    
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
                
                # Button to use suggested quantity
                if st.button("✅ 使用建議數量", key="btn_use_sltp_qty"):
                    st.session_state["deploy_qty_override"] = result['max_qty']
                    st.session_state["deploy_ticker_override"] = ticker
                    st.session_state["deploy_price_override"] = calc_entry_price
                    st.success(f"已設定數量為 {result['max_qty']:.2f}，請在下方確認並加入清單")
                    st.rerun()

        # 操作區塊
        with st.container(border=True):
            col_act1, col_act2, col_act3, col_act4 = st.columns([1.5, 1, 1, 1])

            # 選擇資產 (現有 or 新增)
            existing_assets = [
                p.get("symbol") or p.get("Ticker") for p in st.session_state.portfolio 
                if (p.get("asset_class") or p.get("Type")) == sel_cat
            ]
            asset_opt = col_act1.selectbox(
                "選擇資產", ["➕ 新增資產..."] + existing_assets, key="deploy_asset_sel"
            )

            target_ticker = ""
            if asset_opt == "➕ 新增資產...":
                # Check if we have an override from SL/TP calculator
                default_ticker = st.session_state.get("deploy_ticker_override", "")
                target_ticker = col_act1.text_input(
                    "輸入新代號", 
                    value=default_ticker,
                    placeholder="如 AAPL", 
                    key="deploy_new_ticker"
                ).upper()
            else:
                target_ticker = asset_opt

            # 輸入交易細節
            # 預設單價 (若是現有資產，抓一下成本當參考)
            ref_price = st.session_state.get("deploy_price_override", 100.0)
            if asset_opt != "➕ 新增資產...":
                ref_item = next(
                    (p for p in st.session_state.portfolio if (p.get("symbol") or p.get("Ticker")) == asset_opt),
                    None,
                )
                if ref_item:
                    ref_price = float(ref_item["Avg_Cost"])

            d_price = col_act2.number_input(
                "單價", 0.0, value=float(ref_price), key="deploy_price"
            )
            
            # Check for quantity override from SL/TP calculator
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

    # --- Step 3: 總結與送出 ---
    if st.session_state.draft_actions:
        st.divider()
        st.markdown("### 3️⃣ 確認並執行 (Step 3)")

        # 顯示清單表格
        draft_df = pd.DataFrame(st.session_state.draft_actions)
        st.dataframe(draft_df, width="stretch", key="draft_actions_table")

        total_planned = draft_df["Total"].sum()
        st.markdown(f"#### 總計畫投入金額: :green[{c_symbol}{total_planned:,.0f}]")

        c_sub1, c_sub2 = st.columns([1, 4])
        if c_sub1.button("🗑️ 清空清單"):
            st.session_state.draft_actions = []
            st.rerun()

        if c_sub2.button("🚀 確認送出 (寫入投資組合)", type="primary"):
            # 執行寫入邏輯
            for action in st.session_state.draft_actions:
                ticker = action["Ticker"]
                # 檢查是否已存在
                existing_idx = next(
                    (
                        i
                        for i, p in enumerate(st.session_state.portfolio)
                        if (p.get("symbol") or p.get("Ticker")) == ticker
                    ),
                    -1,
                )

                if existing_idx >= 0:
                    # 更新現有
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
                    # 新增
                    # 需猜測幣別 (簡單邏輯)
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
                            "account_id": "default_main", # Default for deployment
                        }
                    )

            save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data)
            st.session_state["force_refresh_market_data"] = True
            st.session_state.draft_actions = []  # 清空
            st.success("交易已成功執行！請至資產清單查看。")
            st.balloons()
            # 這裡可以選擇是否 rerun，或讓使用者自己切換頁面

    else:
        st.info("尚未加入任何交易計畫。")



# ===========================
# 4. 帳戶管理
# ===========================
def render_account_manager():
    st.subheader("🏦 帳戶管理")
    
    if "accounts" not in st.session_state:
        st.session_state.accounts = []
        
    accounts = st.session_state.accounts
    
    # List Accounts
    for i, acc in enumerate(accounts):
        with st.expander(f"{acc['name']} ({acc['type']})", expanded=False):
            c1, c2 = st.columns(2)
            new_name = c1.text_input("帳戶名稱", acc['name'], key=f"acc_name_{i}")
            new_type = c2.selectbox("帳戶類型", config.ui.account_types, index=config.ui.account_types.index(acc['type']) if acc['type'] in config.ui.account_types else 0, key=f"acc_type_{i}")
            
            if st.button("更新", key=f"acc_upd_{i}"):
                acc['name'] = new_name
                acc['type'] = new_type
                save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data)
                st.success("已更新")
                st.rerun()
                
            if len(accounts) > 1 and st.button("刪除", key=f"acc_del_{i}"):
                # Check for assets?
                # For now just force delete and assets will point to missing ID (migrated to default next load? or zombie)
                # Ideally warn user.
                accounts.pop(i)
                save_accounts(st.session_state.accounts)
                st.success("已刪除")
                st.rerun()

    st.divider()
    st.markdown("### ➕ 新增帳戶")
    with st.form("new_acc_form"):
        c1, c2 = st.columns(2)
        n_name = c1.text_input("帳戶名稱")
        n_type = c2.selectbox("帳戶類型", config.ui.account_types)
        
        if st.form_submit_button("新增帳戶"):
            if n_name:
                import uuid
                new_acc = {
                    "id": str(uuid.uuid4()),
                    "name": n_name,
                    "type": n_type,
                    "currency": "TWD"
                }
                st.session_state.accounts.append(new_acc)
                save_accounts(st.session_state.accounts)
                st.success(f"已新増 {n_name}")
                st.rerun()
            else:
                st.error("請輸入名稱")


# ===========================
# 主入口
# ===========================
def render_asset_list_section(df_market_data, c_symbol):
    st.subheader("📋 資產清單管理")

    if not st.session_state.portfolio:
        st.info("目前無資產。")
        return

    # Prepare Data
    df_raw = pd.DataFrame(st.session_state.portfolio)
    df_raw["Original_Index"] = df_raw.index
    
    # Normalize 'Ticker' column for merging
    if "symbol" in df_raw.columns:
        df_raw["Ticker"] = df_raw["symbol"]
    elif "Ticker" not in df_raw.columns:
        df_raw["Ticker"] = ""
        
    # Also normalize other keys if needed by UI later
    if "asset_class" in df_raw.columns and "Type" not in df_raw.columns:
        df_raw["Type"] = df_raw["asset_class"]

    if not df_market_data.empty:
        # Select only columns that exist in df_market_data
        merge_cols = [
            "Ticker", "Market_Value", "Avg_Cost", 
            "Current_Price", "Last_Update", "ROI (%)", "Status",
            "Display_Price", "Display_Cost_Basis", "Display_Market_Value", 
            "Display_Total_Cost", "Display_PL", "Display_Currency"
        ]
        merge_cols = [c for c in merge_cols if c in df_market_data.columns]
        
        df_merged = pd.merge(
            df_raw, df_market_data[merge_cols], on="Ticker", how="left"
        )
        
        # Use converted Avg_Cost from market data if available
        if "Avg_Cost_y" in df_merged.columns:
            df_merged["Avg_Cost"] = df_merged["Avg_Cost_y"].fillna(df_merged["Avg_Cost_x"])

        df_merged["Market_Value"] = df_merged["Market_Value"].fillna(0)
        
        # Add missing columns
        if "Current_Price" not in df_merged.columns:
            df_merged["Current_Price"] = 0
        else:
            df_merged["Current_Price"] = df_merged["Current_Price"].fillna(0)
        
        if "Last_Update" not in df_merged.columns:
            df_merged["Last_Update"] = "N/A"
        else:
            df_merged["Last_Update"] = df_merged["Last_Update"].fillna("N/A")
    else:
        df_merged = df_raw
        df_merged["Market_Value"] = 0
        df_merged["Current_Price"] = 0
        df_merged["Last_Update"] = "N/A"

    # Account Name Mapping
    accounts_map = {
        acc.get("account_id") or acc.get("id"): acc.get("name") 
        for acc in st.session_state.get("accounts", [])
    }
    name_to_id_map = {v: k for k, v in accounts_map.items()}

    # Ensure columns are clean strings
    df_merged.columns = df_merged.columns.astype(str).str.strip()
    df_merged = df_merged.loc[:, ~df_merged.columns.duplicated()]

    # Ensure Account_ID exists
    if "Account_ID" not in df_merged.columns:
        df_merged["Account_ID"] = "default_main"

    # Fill missing IDs
    df_merged["Account_ID"] = df_merged["Account_ID"].fillna("default_main")
    
    # Create editable columns
    df_merged["Account_Name"] = df_merged["Account_ID"].map(lambda x: accounts_map.get(x, "未知"))
    
    # Normalize Quantity/Avg_Cost to Title Case if needed for Editor consistency
    if "quantity" in df_merged.columns and "Quantity" not in df_merged.columns:
         df_merged["Quantity"] = df_merged["quantity"]
    if "Quantity" not in df_merged.columns:
         df_merged["Quantity"] = 0.0

    if "avg_cost" in df_merged.columns and "Avg_Cost" not in df_merged.columns:
         df_merged["Avg_Cost"] = df_merged["avg_cost"]
    if "Avg_Cost" not in df_merged.columns:
         df_merged["Avg_Cost"] = 0.0

    # Add Selection Column
    df_merged["Select"] = False
    
    # Selection Mode
    st.info("💡 直接編輯表格內容可即時修改 (數量、成本、類別等)。勾選 [選擇] 欄位可進行進階操作 (風控、加減倉)。")

    # Use a static key to prevent reloading on typing, but we need to handle the state.
    editor_key = "asset_manager_editor_v2"

    edited_df = st.data_editor(
        df_merged,
        key=editor_key,
        column_order=[
            "Select", "Type", "Ticker", "Display_Currency", "Display_Price", 
            "Quantity", "Avg_Cost",
            "Account_Name",
            "Display_Market_Value", 
            "Display_Total_Cost", "Display_PL", "ROI (%)", 
            "Last_Update", "Status"
        ],
        column_config={
            "Select": st.column_config.CheckboxColumn("選擇", width="small", default=False),
            "Type": st.column_config.SelectboxColumn("類別", options=config.ui.asset_types, width="small", required=True),
            "Ticker": st.column_config.TextColumn("代號", width="small", required=True, validate="^[A-Za-z0-9.-]+$"),
            "Display_Currency": st.column_config.TextColumn("幣別", width="small", disabled=True),
            "Display_Price": st.column_config.NumberColumn("現價", format="%.2f", disabled=True),
            "Quantity": st.column_config.NumberColumn("持倉", min_value=0, step=0.0001, format="%.4f", required=True),
            "Avg_Cost": st.column_config.NumberColumn("均價", min_value=0, step=0.01, format="%.2f", required=True),
            "Account_Name": st.column_config.SelectboxColumn("帳戶", options=list(accounts_map.values()), width="small", required=True),
            "Display_Market_Value": st.column_config.NumberColumn("市值", format="%.0f", disabled=True),
            "Display_Total_Cost": st.column_config.NumberColumn("總成本", format="%.0f", disabled=True),
            "Display_PL": st.column_config.NumberColumn("損益", format="%.0f", disabled=True),
            "ROI (%)": st.column_config.NumberColumn("ROI", format="%.1f%%", disabled=True),
            "Last_Update": st.column_config.TextColumn("更新時間", width="medium", disabled=True),
            "Status": st.column_config.TextColumn("狀態", width="small", disabled=True),
        },
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
    )

    # Change Detection Logic (Same as thought process)
    changes_detected = False
    selected_item = None
    selected_idx = -1

    for i, row in edited_df.iterrows():
        orig_idx = int(row["Original_Index"])
        if orig_idx < len(st.session_state.portfolio):
            asset = st.session_state.portfolio[orig_idx]
            
            # Check for Selection
            if row["Select"]:
                selected_item = asset
                selected_idx = orig_idx
                # We don't break here to allow saving other edits if any
            
            # Helper to update if changed
            def update_if_changed(key_main, key_legacy, new_val, is_float=False):
                old_val = asset.get(key_main) or asset.get(key_legacy)
                # handle None
                if old_val is None: old_val = 0.0 if is_float else ""
                
                changed = False
                if is_float:
                    if abs(float(new_val) - float(old_val)) > 0.0001: changed = True
                else:
                    if str(new_val) != str(old_val): changed = True
                
                if changed:
                    asset[key_main] = new_val
                    if key_legacy in asset: asset[key_legacy] = new_val
                    return True
                return False

            c1 = update_if_changed("quantity", "Quantity", float(row["Quantity"]), True)
            c2 = update_if_changed("avg_cost", "Avg_Cost", float(row["Avg_Cost"]), True)
            c3 = update_if_changed("symbol", "Ticker", row["Ticker"], False)
            c4 = update_if_changed("asset_class", "Type", row["Type"], False)
            
            c5 = False
            new_acc_name = row["Account_Name"]
            if new_acc_name in name_to_id_map:
                new_acc_id = name_to_id_map[new_acc_name]
                old_acc_id = asset.get("account_id") or asset.get("Account_ID", "default_main")
                if new_acc_id != old_acc_id:
                    asset["account_id"] = new_acc_id
                    if "Account_ID" in asset: asset["Account_ID"] = new_acc_id
                    c5 = True
            
            if c1 or c2 or c3 or c4 or c5:
                changes_detected = True

    if changes_detected:
        save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data)
        st.session_state["force_refresh_market_data"] = True
        st.toast("✅ 資產資料已更新", icon="💾")
        st.rerun()

    # Handle Selection
    if selected_item and selected_idx != -1:
         asset_action_dialog(selected_idx, selected_item)



def render_manager(df_market_data, c_symbol, total_val):
    inject_custom_css()
    sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs(
        ["📝 資產清單管理", "💰 資金投入與部署", "🎯 配置目標設定", "🏦 帳戶管理"]
    )

    with sub_tab1:
        render_asset_list_section(df_market_data, c_symbol)
    with sub_tab2:
        render_calculator_section(df_market_data, c_symbol, total_val)
    with sub_tab3:
        render_allocation_section()
    with sub_tab4:
        render_account_manager()

    st.markdown('<div class="fab-container">', unsafe_allow_html=True)
    if st.button("➕", key="fab_add"):
        add_asset_dialog()
    st.markdown("</div>", unsafe_allow_html=True)
