"""
Settings UI Module.

This module provides the Settings & Configuration page for managing
accounts and asset allocation targets.
"""

import streamlit as st
import pandas as pd
import uuid
from datetime import datetime
from modules.data_loader import save_all_data
from config import get_config

config = get_config()


def render_account_manager():
    """Render account management section."""
    st.subheader("🏦 Account Management")
    st.caption("Manage your investment, cash, and liability accounts.")
    
    if "accounts" not in st.session_state:
        st.session_state.accounts = []
        
    accounts = st.session_state.accounts
    
    # List existing accounts
    if accounts:
        for i, acc in enumerate(accounts):
            acc_type = acc.get('account_type') or acc.get('type', 'Other')
            with st.expander(f"📁 {acc['name']} ({acc_type})", expanded=False):
                c1, c2 = st.columns(2)
                new_name = c1.text_input("Account Name", acc['name'], key=f"acc_name_{i}")

                try:
                    type_idx = config.ui.account_types.index(acc_type)
                except ValueError:
                    type_idx = 0
                new_type = c2.selectbox("Account Type", config.ui.account_types, index=type_idx, key=f"acc_type_{i}")
                
                c3, c4 = st.columns(2)
                new_institution = c3.text_input("Institution", acc.get('institution', ''), key=f"acc_inst_{i}")
                new_acc_num = c4.text_input("Last 4 Digits", acc.get('account_number', ''), key=f"acc_num_{i}", max_chars=4)
                
                c5, c6 = st.columns(2)
                current_curr = acc.get('base_currency') or acc.get('currency', 'TWD')
                new_curr = c5.selectbox("Base Currency", ["TWD", "USD"], index=0 if current_curr == 'TWD' else 1, key=f"acc_curr_{i}")
                new_active = c6.checkbox("Active", acc.get('is_active', True), key=f"acc_active_{i}")
                
                new_desc = st.text_area("Description", acc.get('description', ''), key=f"acc_desc_{i}", height=80)
                
                c_btn1, c_btn2 = st.columns(2)
                if c_btn1.button("✅ Update", key=f"acc_upd_{i}", use_container_width=True):
                    acc.update({
                        'name': new_name, 'account_type': new_type, 'type': new_type,
                        'institution': new_institution, 'account_number': new_acc_num,
                        'base_currency': new_curr, 'currency': new_curr,
                        'is_active': new_active, 'description': new_desc
                    })
                    save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data, st.session_state.get("loan_plans", []))
                    st.toast("Account updated!", icon="✅")
                    st.rerun()
                        
                if len(accounts) > 1 and c_btn2.button("🗑️ Delete", key=f"acc_del_{i}", use_container_width=True):
                    accounts.pop(i)
                    save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data, st.session_state.get("loan_plans", []))
                    st.toast("Account deleted!", icon="🗑️")
                    st.rerun()
    
    st.divider()
    
    # Add new account
    st.markdown("### ➕ Add New Account")
    with st.form("new_acc_form"):
        c1, c2 = st.columns(2)
        n_name = c1.text_input("Account Name", placeholder="e.g. Firstrade")
        n_type = c2.selectbox("Type", config.ui.account_types)
        
        c3, c4 = st.columns(2)
        n_institution = c3.text_input("Institution", placeholder="e.g. Schwab, TD")
        n_acc_num = c4.text_input("Last 4 Digits", placeholder="Optional", max_chars=4)
        
        c5, c6 = st.columns(2)
        n_curr = c5.selectbox("Currency", ["TWD", "USD"], index=0)
        n_active = c6.checkbox("Active", value=True)
        
        n_desc = st.text_area("Description", height=80)
        
        if st.form_submit_button("Create Account", type="primary", use_container_width=True):
            if n_name:
                new_id = f"acc_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                st.session_state.accounts.append({
                    "id": new_id, "account_id": new_id,
                    "name": n_name, "account_type": n_type, "type": n_type,
                    "institution": n_institution, "account_number": n_acc_num,
                    "base_currency": n_curr, "currency": n_curr,
                    "is_active": n_active, "description": n_desc,
                    "created_date": datetime.now().strftime("%Y-%m-%d")
                })
                save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data, st.session_state.get("loan_plans", []))
                st.toast(f"Account {n_name} created!", icon="✨")
                st.rerun()
            else:
                st.error("Account Name is required")


def render_allocation_section():
    """Render asset allocation targets configuration."""
    st.subheader("🎯 Target Allocation")
    st.caption("Set your desired portfolio weights.")
    
    current_types = set([p.get("asset_class") or p.get("Type") for p in st.session_state.portfolio])
    # Ensure default types are present
    all_types = list(current_types.union({"美股", "台股", "虛擬貨幣", "現金", "負債"}))
    # Filter out empty if any
    all_types = [t for t in all_types if t]

    new_targets = {}
    total_pct = 0.0

    cols = st.columns(4)
    for i, cat in enumerate(all_types):
        col = cols[i % 4]
        cur_val = st.session_state.allocation_targets.get(cat, 0.0)
        val = col.number_input(f"{cat} (%)", 0.0, 100.0, float(cur_val), step=5.0, key=f"alloc_{cat}")
        new_targets[cat] = val
        total_pct += val

    st.divider()

    c_bar, c_info = st.columns([4, 1])
    with c_bar:
        st.progress(min(total_pct / 100, 1.0))

    with c_info:
        if total_pct > 100: st.markdown(f"🚫 :red[**{total_pct:.1f}%**]")
        elif total_pct == 100: st.markdown(f"✅ :green[**{total_pct:.1f}%**]")
        else: st.markdown(f"⚠️ **{total_pct:.1f}%**")

    if st.button("💾 Save Targets", type="primary", use_container_width=True, disabled=(total_pct > 100)):
        st.session_state.allocation_targets = new_targets
        save_all_data(st.session_state.accounts, st.session_state.portfolio, st.session_state.allocation_targets, st.session_state.history_data, st.session_state.get("loan_plans", []))
        st.toast("Targets saved!", icon="💾")
        st.rerun()


def render_settings():
    """
    Main entry point for Settings page.
    """
    st.title("⚙️ Settings")
    
    tab1, tab2 = st.tabs(["🏦 Accounts", "🎯 Allocation"])
    
    with tab1:
        render_account_manager()
    
    with tab2:
        render_allocation_section()
