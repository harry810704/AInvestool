"""
Asset Management UI Module.

This module provides the dedicated Asset Management page with full CRUD operations
for portfolio assets including buy, sell, edit, delete, and transfer functions.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from modules.data_loader import save_all_data
from modules.market_service import search_yahoo_ticker, fetch_single_price
from models import Account
from config import get_config

config = get_config()


def check_is_outdated(last_update_str):
    """Check if asset data is outdated (>24h)."""
    if not last_update_str or last_update_str == "N/A":
        return True
    try:
        from datetime import timedelta
        last_update_dt = datetime.strptime(last_update_str, "%Y-%m-%d %H:%M")
        return datetime.now() - last_update_dt > timedelta(days=1)
    except:
        return True


@st.dialog("⚙️ 資產管理與交易")
def asset_action_dialog(index, asset):
    """
    Asset action dialog for buy/sell/edit/delete/transfer operations.
    
    Args:
        index: Asset index in portfolio
        asset: Asset dictionary
    """
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

    # Tabs for different actions
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
                
                save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data, st.session_state.get("loan_plans", []))
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

        if st.button("確認減倉", key=f"btn_sell_{index}", type="primary", use_container_width=True):
            if sell_qty > 0:
                asset["quantity"] = qty - sell_qty
                if asset["quantity"] < 0: asset["quantity"] = 0
                
                if "Quantity" in asset: asset["Quantity"] = asset["quantity"]
                
                save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data, st.session_state.get("loan_plans", []))
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
        
        curr_acc_id = asset.get("account_id") or asset.get("Account_ID", "default_main")
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
            
            save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data, st.session_state.get("loan_plans", []))
            st.session_state["force_refresh_market_data"] = True
            st.success("數據已更新")
            st.rerun()

    with tab_move:
        st.markdown("#### 無損移轉 (不影響損益)")
        st.caption("將資產移動至另一個帳戶，例如：從主要帳戶移動至美股帳戶。")
        
        accounts = st.session_state.get("accounts", [])
        acc_options = {acc["name"]: str(acc.get("account_id") or acc.get("id")) for acc in accounts} if accounts else {"主要帳戶": "default_main"}
        curr_acc_id = asset.get("account_id") or asset.get("Account_ID", "default_main")
        
        target_acc_names = [name for name, aid in acc_options.items() if aid != curr_acc_id]
        
        if not target_acc_names:
            st.info("沒有其他帳戶可供移轉。請先新增帳戶。")
        else:
            target_name = st.selectbox("移轉至目標帳戶", target_acc_names, key=f"move_acc_{index}")
            
            if st.button("確認移轉", key=f"btn_move_{index}", type="primary", use_container_width=True):
                target_id = acc_options[target_name]
                asset["account_id"] = target_id
                if "Account_ID" in asset: asset["Account_ID"] = target_id
                
                save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data, st.session_state.get("loan_plans", []))
                st.session_state["force_refresh_market_data"] = True
                st.success(f"已移轉至 {target_name}")
                st.rerun()

    with tab_risk:
        st.markdown("### 🎯 ATR 風控建議")
        st.caption(f"根據 ATR (平均真實波動區間) 計算停損停利建議")
        
        col_info1, col_info2 = st.columns(2)
        col_info1.metric("代號", ticker)
        col_info2.metric("平均成本", f"{asset.get('currency', 'USD')} {avg_cost:.2f}")
        
        current_price = asset.get("manual_price")
        if current_price is None: current_price = asset.get("Manual_Price", 0.0)
        
        if current_price == 0:
            current_price = avg_cost
        
        col_info1.metric("當前價格", f"{asset.get('currency', 'USD')} {current_price:.2f}")
        col_info2.metric("持有數量", f"{qty:.2f}")
        
        st.divider()
        
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
        
        if st.button("🔍 計算建議線", key=f"calc_risk_{index}", type="primary"):
            from modules.risk_management import suggest_sl_tp_for_holding
            
            with st.spinner(f"正在計算 {ticker} 的風控建議..."):
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
        
        if f"risk_calc_{index}" in st.session_state:
            result = st.session_state[f"risk_calc_{index}"]
            
            st.divider()
            st.markdown("### 📊 計算結果")
            
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
            
            col_sl, col_tp = st.columns(2)
            col_sl.markdown(f"""
            <div style='background-color: #ffebee; padding: 15px; border-radius: 10px; border-left: 4px solid #f44336;'>
                <h4 style='margin: 0; color: #c62828;'>🔴 建議停損 (SL)</h4>
                <h2 style='margin: 5px 0; color: #c62828;'>{curr} {result['sl_price']:.2f}</h2>
                <p style='margin: 0; font-size: 12px; color: #666;'>風險: {result['current_risk']:.2f}</p>
            </div>
            """, unsafe_allow_html=True)
            
            col_tp.markdown(f"""
            <div style='background-color: #e8f5e9; padding: 15px; border-radius: 10px; border-left: 4px solid #4caf50;'>
                <h4 style='margin: 0; color: #2e7d32;'>🟢 建議停利 (TP)</h4>
                <h2 style='margin: 5px 0; color: #2e7d32;'>{curr} {result['tp_price']:.2f}</h2>
                <p style='margin: 0; font-size: 12px; color: #666;'>目標: {result['current_reward']:.2f}</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.divider()
            
            if st.button("💾 應用建議並儲存", key=f"save_risk_{index}", type="primary"):
                asset["suggested_sl"] = result['sl_price']
                asset["suggested_tp"] = result['tp_price']
                if "Suggested_SL" in asset: asset["Suggested_SL"] = result['sl_price']
                if "Suggested_TP" in asset: asset["Suggested_TP"] = result['tp_price']
                
                save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data, st.session_state.get("loan_plans", []))
                st.success(f"✅ 已儲存 {ticker} 的停損停利建議！")
                st.rerun()

    with tab_del:
        st.warning("⚠️ 刪除操作無法復原！")
        if st.button("❌ 確認刪除", key=f"btn_del_{index}", type="primary"):
            st.session_state.portfolio.pop(index)
            save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data, st.session_state.get("loan_plans", []))
            st.session_state["force_refresh_market_data"] = True
            st.rerun()


@st.dialog("➕ 新增資產")
def add_asset_dialog():
    """Dialog for adding new assets to portfolio."""
    st.caption("新增資產或負債項目")
    
    # Select Type and Account
    c_type, c_acc = st.columns(2)
    with c_type:
        atype = st.selectbox("資產類別", config.ui.asset_types)
    with c_acc:
        accounts = st.session_state.get("accounts", [])
        acc_options = {acc["name"]: str(acc.get("account_id") or acc.get("id")) for acc in accounts} if accounts else {"主要帳戶": "default_main"}
        sel_acc_name = st.selectbox("所屬帳戶", list(acc_options.keys()))
        sel_acc_id = acc_options[sel_acc_name]

    is_financial = atype in ["現金", "負債"]
    ticker = ""
    
    if is_financial:
        # Cash/Liability flow
        c_name, c_curr = st.columns([2, 1])
        with c_name:
            custom_name = st.text_input("項目名稱 (選填)", placeholder="例如：房貸、定存")
        with c_curr:
            curr = st.selectbox("幣別", ["USD", "TWD"], index=1)
            
        c_amt, c_ph = st.columns([2, 1])
        amount = c_amt.number_input("金額/餘額", min_value=0.0, value=0.0, step=1000.0)
        
        # Loan plan option
        create_plan = False
        plan_rate = 0.0
        plan_years = 0
        plan_start = datetime.now().date()
        
        if atype == "負債":
            st.markdown("---")
            create_plan = st.toggle("規劃還款計劃?", value=False)
            
            if create_plan:
                with st.container(border=True):
                    st.caption("還款計劃設定 (本息攤還試算)")
                    lp1, lp2, lp3 = st.columns(3)
                    plan_rate = lp1.number_input("年利率 (%)", min_value=0.0, value=2.0, step=0.1)
                    plan_years = lp2.number_input("還款年限", min_value=1, value=20, step=1)
                    plan_start = lp3.date_input("開始日期", value=datetime.now())
                    
                    if st.button("📊 試算還款表", key="btn_calc_plan"):
                        from modules.loan_service import calculate_amortization_schedule
                        schedule = calculate_amortization_schedule(amount, plan_rate, plan_years * 12, str(plan_start))
                        if schedule:
                            first_pmt = schedule[0].payment_amount
                            total_interest = sum(item.interest_paid for item in schedule)
                            st.info(f"首期還款: {first_pmt:,.0f} | 總利息: {total_interest:,.0f}")
                            
                            df_sch = pd.DataFrame([s.to_dict() for s in schedule])
                            st.line_chart(df_sch, x="payment_number", y="remaining_balance", height=200)
    else:
        # Investment assets flow
        st.markdown("---")
        c_s, c_r = st.columns([2, 3])
        q = c_s.text_input("搜尋代號", placeholder="輸入如: TSLA, 2330...")
        sel_search = c_r.selectbox("搜尋結果", search_yahoo_ticker(q) if q else [])
        
        auto_t = sel_search.split(" | ")[0] if sel_search else ""
        
        c1, c2, c3 = st.columns(3)
        ticker = c1.text_input("代號", value=auto_t).upper()
        curr = c2.selectbox("幣別", ["USD", "TWD"], index=0)
        qty = c3.number_input("持有數量", min_value=0.0, value=1.0, step=0.1)
        
        cost = st.number_input("平均成本 (單價)", min_value=0.0, value=100.0, step=0.1)
        amount = 0

    st.markdown("---")
    if st.button("確認新增", type="primary", use_container_width=True):
        if not is_financial and not ticker:
            st.error("請輸入代號")
            return
            
        new_id = f"ast_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        new_asset = {
            "asset_id": new_id,
            "asset_class": atype,
            "account_id": sel_acc_id,
            "currency": curr,
            "last_update": "N/A",
            "manual_price": 0.0, 
        }
        
        if is_financial:
            prefix = "CASH" if atype == "現金" else "DEBT"
            final_ticker = f"{prefix}-{curr}" 
            if custom_name:
                 new_asset["name"] = custom_name
            
            new_asset["symbol"] = final_ticker
            new_asset["quantity"] = amount
            new_asset["avg_cost"] = 1.0
        else:
            new_asset["symbol"] = ticker
            new_asset["quantity"] = qty
            new_asset["avg_cost"] = cost
            
        st.session_state.portfolio.append(new_asset)
        
        if is_financial and create_plan:
            from modules.loan_service import create_loan_plan
            
            new_plan = create_loan_plan(
                asset_id=new_id,
                total_amount=amount,
                annual_rate=plan_rate,
                period_months=plan_years * 12,
                start_date=str(plan_start)
            )
            
            if "loan_plans" not in st.session_state:
                st.session_state.loan_plans = []
            st.session_state.loan_plans.append(new_plan.to_dict())
            
        save_all_data(
            st.session_state.accounts, 
            st.session_state.portfolio, 
            st.session_state.allocation_targets, 
            st.session_state.history_data,
            st.session_state.get("loan_plans", [])
        )
        st.session_state["force_refresh_market_data"] = True
        st.success(f"已新增 {atype} 項目")
        st.rerun()


def render_asset_list_section(df_market_data, c_symbol):
    """
    Render asset list management section with inline editing.
    
    Args:
        df_market_data: Market data DataFrame
        c_symbol: Currency symbol for display
    """
    st.subheader("📋 資產清單管理")
    
    if st.button("➕ 新增資產", key="btn_add_new_asset", type="primary"):
        add_asset_dialog()

    if not st.session_state.portfolio:
        st.info("目前無資產。")
        return

    # Prepare data
    df_raw = pd.DataFrame(st.session_state.portfolio)
    df_raw["Original_Index"] = df_raw.index
    
    # Normalize columns
    if "symbol" in df_raw.columns:
        df_raw["Ticker"] = df_raw["symbol"]
    elif "Ticker" not in df_raw.columns:
        df_raw["Ticker"] = ""
        
    if "asset_class" in df_raw.columns and "Type" not in df_raw.columns:
        df_raw["Type"] = df_raw["asset_class"]

    if "quantity" in df_raw.columns:
         df_raw["Quantity"] = df_raw["quantity"]
    elif "Quantity" not in df_raw.columns:
         df_raw["Quantity"] = 0.0

    if "avg_cost" in df_raw.columns:
         df_raw["Avg_Cost"] = df_raw["avg_cost"]
    elif "Avg_Cost" not in df_raw.columns:
         df_raw["Avg_Cost"] = 0.0

    # Merge with market data
    if not df_market_data.empty:
        merge_cols = [
            "Ticker", "Market_Value",
            "Current_Price", "Last_Update", "ROI (%)", "Status",
            "Display_Price", "Display_Cost_Basis", "Display_Market_Value", 
            "Display_Total_Cost", "Display_PL", "Display_Currency"
        ]
        merge_cols = [c for c in merge_cols if c in df_market_data.columns]
        
        df_merged = pd.merge(
            df_raw, df_market_data[merge_cols], on="Ticker", how="left"
        )
        
        if "Avg_Cost" not in df_merged.columns:
             df_merged["Avg_Cost"] = 0.0

        df_merged["Market_Value"] = df_merged["Market_Value"].fillna(0)
        
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

    # Account mapping
    accounts_map = {
        acc.get("account_id") or acc.get("id"): acc.get("name") 
        for acc in st.session_state.get("accounts", [])
    }
    name_to_id_map = {v: k for k, v in accounts_map.items()}

    df_merged.columns = df_merged.columns.astype(str).str.strip()
    df_merged = df_merged.loc[:, ~df_merged.columns.duplicated()]

    if "Account_ID" not in df_merged.columns:
        df_merged["Account_ID"] = "default_main"

    df_merged["Account_ID"] = df_merged["Account_ID"].fillna("default_main")
    df_merged["Account_Name"] = df_merged["Account_ID"].map(lambda x: accounts_map.get(x, "未知"))
    df_merged["Select"] = False
    
    st.info("💡 直接編輯表格內容可即時修改 (數量、成本、類別等)。勾選 [選擇] 欄位可進行進階操作 (風控、加減倉)。")

    editor_key = "asset_manager_editor_v2_fixed"

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

    # Change detection
    changes_detected = False
    selected_items = []

    for i, row in edited_df.iterrows():
        orig_idx = int(row["Original_Index"])
        if orig_idx < len(st.session_state.portfolio):
            asset = st.session_state.portfolio[orig_idx]
            
            if row["Select"]:
                selected_items.append((orig_idx, asset))
            
            def update_if_changed(key_main, key_legacy, new_val, is_float=False):
                old_val = asset.get(key_main) or asset.get(key_legacy)
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
        save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data, st.session_state.get("loan_plans", []))
        st.session_state["force_refresh_market_data"] = True
        st.toast("✅ 資產資料已更新", icon="💾")
        st.rerun()

    # Handle selection
    if selected_items:
        idx, item = selected_items[0]
        
        st.markdown(f"**已選擇:** `{item.get('symbol', 'Unknown')}`")
        if st.button("🛠️ 管理此資產 (買/賣/風控)", type="primary", key="btn_open_manage_dialog"):
            asset_action_dialog(idx, item)
            
        if len(selected_items) > 1:
            st.caption("⚠️ 偵測到多選，僅開啟第一項。")


def render_asset_management(df_market_data, c_symbol):
    """
    Main entry point for Asset Management page.
    
    Args:
        df_market_data: Market data DataFrame
        c_symbol: Currency symbol for display
    """
    st.title("💼 資產管理")
    st.caption("管理您的投資組合 - 新增、編輯、交易資產")
    
    render_asset_list_section(df_market_data, c_symbol)
