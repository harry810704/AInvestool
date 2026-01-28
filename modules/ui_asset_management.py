"""
Asset Management UI Module.

This module provides the dedicated Asset Management page with full CRUD operations
for portfolio assets including buy, sell, edit, delete, and transfer functions.
"""

import streamlit as st
import pandas as pd
import html
from datetime import datetime
from modules.data_loader import save_all_data
from modules.market_service import search_yahoo_ticker, fetch_single_price
from models import Account
from config import get_config

config = get_config()

@st.dialog("⚙️ Asset Actions")
def asset_action_dialog(index, asset):
    """
    Asset action dialog for buy/sell/edit/delete/transfer operations.
    """
    # Map legacy keys if present
    ticker = asset.get("symbol") or asset.get("Ticker")
    atype = asset.get("asset_class") or asset.get("Type")
    curr = asset.get("currency") or asset.get("Currency")
    avg_cost = float(asset.get("avg_cost") or asset.get("Avg_Cost", 0.0))
    qty = float(asset.get("quantity") or asset.get("Quantity", 0.0))
    
    safe_ticker = html.escape(str(ticker))
    safe_atype = html.escape(str(atype))
    safe_curr = html.escape(str(curr))

    st.markdown(f"### {safe_ticker}")
    st.markdown(f"<span style='color: #94A3B8'>{safe_atype} | {safe_curr}</span>", unsafe_allow_html=True)
    st.divider()

    # Tabs for different actions
    tab_buy, tab_sell, tab_edit, tab_move, tab_risk, tab_del = st.tabs(
        ["Buy", "Sell", "Edit", "Transfer", "Risk", "Delete"]
    )

    with tab_buy:
        c1, c2 = st.columns(2)
        add_qty = c1.number_input("Qty to Buy", min_value=0.0, value=0.0, step=0.1, key=f"bq_{index}")
        add_price = c2.number_input(
            f"Price ({curr})",
            min_value=0.0,
            value=float(avg_cost),
            key=f"bp_{index}",
        )

        st.caption(f"Estimated Cost: {curr} {add_qty * add_price:,.2f}")

        if st.button("Confirm Buy", key=f"btn_buy_{index}", type="primary", use_container_width=True):
            if add_qty > 0:
                old_cost = qty * avg_cost
                new_qty = qty + add_qty
                new_avg = ((old_cost + (add_qty * add_price)) / new_qty) if new_qty else 0

                st.session_state.portfolio[index]["avg_cost"] = new_avg
                st.session_state.portfolio[index]["quantity"] = new_qty
                
                # Cleanup legacy
                if "Avg_Cost" in st.session_state.portfolio[index]: del st.session_state.portfolio[index]["Avg_Cost"]
                if "Quantity" in st.session_state.portfolio[index]: del st.session_state.portfolio[index]["Quantity"]
                
                save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data, st.session_state.get("loan_plans", []))
                st.session_state["force_refresh_market_data"] = True
                st.toast("Buy order executed!", icon="✅")
                st.rerun()
            else:
                st.error("Quantity must be > 0")

    with tab_sell:
        sell_qty = st.number_input(
            "Qty to Sell",
            min_value=0.0,
            max_value=float(qty),
            value=0.0,
            step=0.1,
            key=f"sq_{index}"
        )

        if st.button("Confirm Sell", key=f"btn_sell_{index}", type="primary", use_container_width=True):
            if sell_qty > 0:
                st.session_state.portfolio[index]["quantity"] = qty - sell_qty
                if st.session_state.portfolio[index]["quantity"] < 0:
                    st.session_state.portfolio[index]["quantity"] = 0
                
                if "Quantity" in st.session_state.portfolio[index]: del st.session_state.portfolio[index]["Quantity"]
                
                save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data, st.session_state.get("loan_plans", []))
                st.session_state["force_refresh_market_data"] = True
                st.toast("Sell order executed!", icon="✅")
                st.rerun()
            else:
                st.error("Quantity must be > 0")

    with tab_edit:
        c1, c2 = st.columns(2)
        fq = c1.number_input("Holding Qty", min_value=0.0, value=float(qty), key=f"fq_{index}")
        fc = c2.number_input("Avg Cost", min_value=0.0, value=float(avg_cost), key=f"fc_{index}")

        accounts = st.session_state.get("accounts", [])
        acc_options = {acc["name"]: str(acc.get("account_id") or acc.get("id")) for acc in accounts} if accounts else {"Main": "default_main"}
        
        curr_acc_id = asset.get("account_id") or asset.get("Account_ID", "default_main")
        acc_names = list(acc_options.keys())
        default_acc_index = 0
        for i, name in enumerate(acc_names):
            if acc_options[name] == curr_acc_id:
                default_acc_index = i
                break

        sel_acc_name = st.selectbox("Account", acc_names, index=default_acc_index, key=f"acc_edit_{index}")

        if st.button("Save Changes", key=f"btn_fix_{index}", use_container_width=True):
            st.session_state.portfolio[index]["quantity"] = fq
            st.session_state.portfolio[index]["avg_cost"] = fc
            st.session_state.portfolio[index]["account_id"] = acc_options[sel_acc_name]
            
            legacy_fields = ["Quantity", "Avg_Cost", "Account_ID"]
            for field in legacy_fields:
                if field in st.session_state.portfolio[index]: del st.session_state.portfolio[index][field]
            
            save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data, st.session_state.get("loan_plans", []))
            st.session_state["force_refresh_market_data"] = True
            st.toast("Asset updated!", icon="💾")
            st.rerun()

    with tab_move:
        current_asset = st.session_state.portfolio[index]
        accounts = st.session_state.get("accounts", [])
        acc_options = {acc["name"]: str(acc.get("account_id") or acc.get("id")) for acc in accounts} if accounts else {"Main": "default_main"}
        curr_acc_id = current_asset.get("account_id") or current_asset.get("Account_ID", "default_main")
        
        target_acc_names = [name for name, aid in acc_options.items() if aid != curr_acc_id]
        
        if not target_acc_names:
            st.info("No other accounts available.")
        else:
            target_name = st.selectbox("Transfer to", target_acc_names, key=f"move_acc_{index}")
            if st.button("Confirm Transfer", key=f"btn_move_{index}", type="primary", use_container_width=True):
                target_id = acc_options[target_name]
                st.session_state.portfolio[index]["account_id"] = target_id
                if "Account_ID" in st.session_state.portfolio[index]: del st.session_state.portfolio[index]["Account_ID"]
                
                save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data, st.session_state.get("loan_plans", []))
                st.session_state["force_refresh_market_data"] = True
                st.toast(f"Transferred to {target_name}", icon="💸")
                st.rerun()

    with tab_risk:
        col_param1, col_param2 = st.columns(2)
        atr_multiplier = col_param1.slider("ATR Mult", 1.0, 5.0, 2.0, 0.5, key=f"atr_mult_{index}")
        r_ratio = col_param2.slider("Risk/Reward", 1.0, 5.0, 2.0, 0.5, key=f"r_ratio_{index}")
        
        if st.button("Calculate Risk Levels", key=f"calc_risk_{index}", type="primary"):
            from modules.risk_management import suggest_sl_tp_for_holding
            current_price = asset.get("manual_price") or asset.get("Manual_Price", 0.0)
            if current_price == 0: current_price = avg_cost
            
            with st.spinner("Calculating..."):
                result = suggest_sl_tp_for_holding(ticker, avg_cost, current_price, atr_multiplier, r_ratio)
                if result:
                    st.session_state[f"risk_calc_{index}"] = result
                    st.rerun()
                else:
                    st.error("Failed to calculate ATR")
        
        if f"risk_calc_{index}" in st.session_state:
            result = st.session_state[f"risk_calc_{index}"]
            col_sl, col_tp = st.columns(2)
            col_sl.metric("Stop Loss", f"{curr} {result['sl_price']:.2f}", f"Risk: {result['current_risk']:.2f}")
            col_tp.metric("Take Profit", f"{curr} {result['tp_price']:.2f}", f"Reward: {result['current_reward']:.2f}")
            
            if st.button("Apply Strategy", key=f"save_risk_{index}", type="primary"):
                st.session_state.portfolio[index]["suggested_sl"] = result['sl_price']
                st.session_state.portfolio[index]["suggested_tp"] = result['tp_price']
                save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data, st.session_state.get("loan_plans", []))
                st.toast("Risk strategy saved!", icon="🛡️")
                st.rerun()

    with tab_del:
        st.warning("Irreversible!")
        if st.button("Delete Asset", key=f"btn_del_{index}", type="primary"):
            st.session_state.portfolio.pop(index)
            save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data, st.session_state.get("loan_plans", []))
            st.session_state["force_refresh_market_data"] = True
            st.rerun()


@st.dialog("➕ Add New Asset")
def add_asset_dialog():
    """Dialog for adding new assets."""
    st.caption("Add investment or liability")
    
    # Select Type and Account
    c_type, c_acc = st.columns(2)
    with c_type:
        atype = st.selectbox("Asset Class", config.ui.asset_types)
    with c_acc:
        accounts = st.session_state.get("accounts", [])
        acc_options = {acc["name"]: str(acc.get("account_id") or acc.get("id")) for acc in accounts} if accounts else {"Main": "default_main"}
        sel_acc_name = st.selectbox("Account", list(acc_options.keys()))
        sel_acc_id = acc_options[sel_acc_name]

    is_financial = atype in ["現金", "負債"]
    ticker = ""
    amount = 0
    qty = 0
    cost = 0
    custom_name = ""
    curr = "USD"
    
    if is_financial:
        c_name, c_curr = st.columns([2, 1])
        with c_name: custom_name = st.text_input("Name (Optional)", placeholder="e.g. Mortgage")
        with c_curr: curr = st.selectbox("Currency", ["USD", "TWD"], index=1)
            
        c_amt, _ = st.columns([2, 1])
        amount = c_amt.number_input("Amount/Balance", min_value=0.0, step=1000.0)
    else:
        c_s, c_r = st.columns([2, 3])
        q = c_s.text_input("Search", placeholder="TSLA...")
        sel_search = c_r.selectbox("Results", search_yahoo_ticker(q) if q else [])
        auto_t = sel_search.split(" | ")[0] if sel_search else ""
        
        c1, c2, c3 = st.columns(3)
        ticker = c1.text_input("Symbol", value=auto_t).upper()
        curr = c2.selectbox("Currency", ["USD", "TWD"], index=0)
        qty = c3.number_input("Quantity", min_value=0.0, value=1.0, step=0.1)
        cost = st.number_input("Avg Cost", min_value=0.0, value=100.0, step=0.1)

    if st.button("Add Asset", type="primary", use_container_width=True):
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
            if custom_name: new_asset["name"] = custom_name
            new_asset["symbol"] = final_ticker
            new_asset["quantity"] = amount
            new_asset["avg_cost"] = 1.0
        else:
            if not ticker:
                st.error("Symbol required")
                return
            new_asset["symbol"] = ticker
            new_asset["quantity"] = qty
            new_asset["avg_cost"] = cost
            
        st.session_state.portfolio.append(new_asset)
        save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data, st.session_state.get("loan_plans", []))
        st.session_state["force_refresh_market_data"] = True
        st.toast("Asset Added", icon="✨")
        st.rerun()


def render_asset_management(df_market_data, c_symbol):
    """
    Main entry point for Asset Management page.
    """
    # Action Bar
    c_title, c_add = st.columns([0.85, 0.15])
    with c_title:
        st.markdown("### 💼 Asset Commander")
    with c_add:
        if st.button("➕ Add Asset", type="primary", use_container_width=True):
            add_asset_dialog()

    if not st.session_state.portfolio:
        st.info("No assets found. Start by adding one.")
        return

    # Prepare Grid Data
    df_raw = pd.DataFrame(st.session_state.portfolio)
    df_raw["Original_Index"] = df_raw.index
    
    # Normalization (Simplified for brevity, assuming standard keys mostly)
    if "symbol" in df_raw.columns: df_raw["Ticker"] = df_raw["symbol"]
    else: df_raw["Ticker"] = ""
    
    if "asset_type" in df_raw.columns: df_raw["Type"] = df_raw["asset_type"]
    elif "asset_class" in df_raw.columns: df_raw["Type"] = df_raw["asset_class"]
    else: df_raw["Type"] = ""

    if "quantity" not in df_raw.columns: df_raw["quantity"] = 0.0
    if "avg_cost" not in df_raw.columns: df_raw["avg_cost"] = 0.0

    df_raw["Quantity"] = df_raw["quantity"]
    df_raw["Avg_Cost"] = df_raw["avg_cost"]

    # Merge Market Data
    if not df_market_data.empty:
        merge_cols = [c for c in ["Ticker", "Market_Value", "Current_Price", "ROI (%)", "Status", "Display_Price", "Display_Market_Value", "Display_PL"] if c in df_market_data.columns]
        df_merged = pd.merge(df_raw, df_market_data[merge_cols], on="Ticker", how="left")
    else:
        df_merged = df_raw
        df_merged["Market_Value"] = 0
        df_merged["ROI (%)"] = 0

    # Account Name
    accounts_map = {acc.get("account_id") or acc.get("id"): acc.get("name") for acc in st.session_state.get("accounts", [])}
    name_to_id_map = {v: k for k, v in accounts_map.items()}

    if "account_id" in df_merged.columns:
        df_merged["Account_ID"] = df_merged["account_id"].fillna("default_main")
    else:
        df_merged["Account_ID"] = "default_main"

    df_merged["Account"] = df_merged["Account_ID"].map(lambda x: accounts_map.get(x, "Unknown"))
    df_merged["Select"] = False

    # Main Grid
    edited_df = st.data_editor(
        df_merged,
        key="asset_grid_v3",
        column_order=[
            "Select", "Type", "Ticker", "Quantity", "Avg_Cost", "Display_Price",
            "Account", "Display_Market_Value", "Display_PL", "ROI (%)"
        ],
        column_config={
            "Select": st.column_config.CheckboxColumn("", width="small"),
            "Type": st.column_config.SelectboxColumn("Type", options=config.ui.asset_types, width="small", required=True),
            "Ticker": st.column_config.TextColumn("Symbol", width="small", required=True),
            "Quantity": st.column_config.NumberColumn("Qty", format="%.4f"),
            "Avg_Cost": st.column_config.NumberColumn("Cost", format="%.2f"),
            "Display_Price": st.column_config.NumberColumn("Price", disabled=True),
            "Account": st.column_config.SelectboxColumn("Account", options=list(accounts_map.values()), width="medium"),
            "Display_Market_Value": st.column_config.NumberColumn("Value", disabled=True),
            "Display_PL": st.column_config.NumberColumn("P/L", disabled=True),
            "ROI (%)": st.column_config.NumberColumn("ROI", format="%.1f%%", disabled=True),
        },
        hide_index=True,
        use_container_width=True,
        height=500
    )

    # Save Changes Logic
    changes = False
    selected = []

    for i, row in edited_df.iterrows():
        orig_idx = int(row["Original_Index"])
        if orig_idx < len(st.session_state.portfolio):
            asset = st.session_state.portfolio[orig_idx]
            
            if row["Select"]: selected.append((orig_idx, asset))
            
            # Simple update logic
            updates = {
                "quantity": float(row["Quantity"]),
                "avg_cost": float(row["Avg_Cost"]),
                "symbol": row["Ticker"],
                "asset_type": row["Type"]
            }
            
            if row["Account"] in name_to_id_map:
                updates["account_id"] = name_to_id_map[row["Account"]]
            
            for k, v in updates.items():
                old_v = asset.get(k)
                if str(v) != str(old_v):
                    asset[k] = v
                    changes = True

    if changes:
        save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data, st.session_state.get("loan_plans", []))
        st.session_state["force_refresh_market_data"] = True
        st.rerun()

    # Contextual Actions for Selected
    if selected:
        idx, item = selected[0]
        # Show bottom sheet / fixed container for actions
        with st.container(border=True):
            st.markdown(f"**Selected: {item.get('symbol')}**")
            if st.button("🛠️ Manage / Trade", type="primary"):
                asset_action_dialog(idx, item)
