"""
Settings UI Module.

This module provides the Settings & Configuration page for managing
accounts and asset allocation targets.
"""

import streamlit as st
import pandas as pd
import uuid
from modules.data_loader import save_all_data
from config import get_config

config = get_config()


def render_account_manager():
    """Render account management section."""
    st.subheader("🏦 帳戶管理")
    st.caption("管理您的帳戶 - 投資帳戶、現金帳戶、信用帳戶等")
    
    if "accounts" not in st.session_state:
        st.session_state.accounts = []
        
    accounts = st.session_state.accounts
    
    # List existing accounts
    if accounts:
        st.markdown("### 現有帳戶")
        for i, acc in enumerate(accounts):
            # Get account_type with backward compatibility
            acc_type = acc.get('account_type') or acc.get('type', '其他')
            with st.expander(f"📁 {acc['name']} ({acc_type})", expanded=False):
                c1, c2 = st.columns(2)
                new_name = c1.text_input("帳戶名稱", acc['name'], key=f"acc_name_{i}")
                # Get current type with backward compatibility
                current_type = acc.get('account_type') or acc.get('type', '其他')
                try:
                    type_idx = config.ui.account_types.index(current_type)
                except ValueError:
                    type_idx = 0
                new_type = c2.selectbox(
                    "帳戶類型", 
                    config.ui.account_types, 
                    index=type_idx, 
                    key=f"acc_type_{i}"
                )
                
                c3, c4 = st.columns(2)
                new_institution = c3.text_input(
                    "金融機構", 
                    acc.get('institution', ''), 
                    key=f"acc_inst_{i}"
                )
                new_acc_num = c4.text_input(
                    "帳號後4碼", 
                    acc.get('account_number', ''), 
                    key=f"acc_num_{i}",
                    max_chars=4
                )
                
                c5, c6 = st.columns(2)
                current_curr = acc.get('base_currency') or acc.get('currency', 'TWD')
                new_curr = c5.selectbox(
                    "基準幣別",
                    ["TWD", "USD"],
                    index=0 if current_curr == 'TWD' else 1,
                    key=f"acc_curr_{i}"
                )
                new_active = c6.checkbox(
                    "啟用",
                    acc.get('is_active', True),
                    key=f"acc_active_{i}"
                )
                
                new_desc = st.text_area(
                    "描述",
                    acc.get('description', ''),
                    key=f"acc_desc_{i}",
                    height=80
                )
                
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    if st.button("✅ 更新", key=f"acc_upd_{i}", use_container_width=True):
                        acc['name'] = new_name
                        acc['account_type'] = new_type
                        acc['type'] = new_type  # Legacy compatibility
                        acc['institution'] = new_institution
                        acc['account_number'] = new_acc_num
                        acc['base_currency'] = new_curr
                        acc['currency'] = new_curr  # Legacy
                        acc['is_active'] = new_active
                        acc['description'] = new_desc
                        save_all_data(
                            st.session_state.accounts, 
                            st.session_state.portfolio, 
                            st.session_state.allocation_targets, 
                            st.session_state.history_data,
                            st.session_state.get("loan_plans", [])
                        )
                        st.success("已更新")
                        st.rerun()
                        
                with col_btn2:
                    if len(accounts) > 1 and st.button("🗑️ 刪除", key=f"acc_del_{i}", use_container_width=True):
                        accounts.pop(i)
                        save_all_data(
                            st.session_state.accounts, 
                            st.session_state.portfolio, 
                            st.session_state.allocation_targets, 
                            st.session_state.history_data,
                            st.session_state.get("loan_plans", [])
                        )
                        st.success("已刪除")
                        st.rerun()
    
    st.divider()
    
    # Add new account
    st.markdown("### ➕ 新增帳戶")
    with st.form("new_acc_form"):
        c1, c2 = st.columns(2)
        n_name = c1.text_input("帳戶名稱", placeholder="例如：Firstrade 美股帳戶")
        n_type = c2.selectbox("帳戶類型", config.ui.account_types)
        
        c3, c4 = st.columns(2)
        n_institution = c3.text_input("金融機構", placeholder="例如：Firstrade, 富邦證券")
        n_acc_num = c4.text_input("帳號後4碼", placeholder="選填", max_chars=4)
        
        c5, c6 = st.columns(2)
        n_curr = c5.selectbox("基準幣別", ["TWD", "USD"], index=0)
        n_active = c6.checkbox("啟用此帳戶", value=True)
        
        n_desc = st.text_area("描述", placeholder="選填：帳戶用途說明", height=80)
        
        if st.form_submit_button("新增帳戶", type="primary", use_container_width=True):
            if n_name:
                from datetime import datetime
                new_id = f"acc_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                new_acc = {
                    "id": new_id,
                    "account_id": new_id,
                    "name": n_name,
                    "account_type": n_type,
                    "type": n_type,  # Legacy compatibility
                    "institution": n_institution,
                    "account_number": n_acc_num,
                    "base_currency": n_curr,
                    "currency": n_curr,  # Legacy compatibility
                    "is_active": n_active,
                    "description": n_desc,
                    "created_date": datetime.now().strftime("%Y-%m-%d")
                }
                st.session_state.accounts.append(new_acc)
                save_all_data(
                    st.session_state.accounts, 
                    st.session_state.portfolio, 
                    st.session_state.allocation_targets, 
                    st.session_state.history_data,
                    st.session_state.get("loan_plans", [])
                )
                st.success(f"已新增 {n_name}")
                st.rerun()
            else:
                st.error("請輸入名稱")


def render_allocation_section():
    """Render asset allocation targets configuration."""
    st.subheader("🎯 投資配置目標設定")
    st.caption("設定各資產類別的目標配置比例")
    
    current_types = set([p.get("asset_class") or p.get("Type") for p in st.session_state.portfolio])
    all_types = list(current_types.union({"美股", "台股", "虛擬貨幣", "現金", "負債"}))
    new_targets = {}
    total_pct = 0.0

    # Create input grid
    st.markdown("#### 配置比例設定")
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

    # Progress bar and validation
    c_bar, c_info = st.columns([4, 1])
    with c_bar:
        st.progress(min(total_pct / 100, 1.0))

    with c_info:
        if total_pct > 100:
            st.markdown(f"🚫 :red[**{total_pct:.1f}%**]")
        elif total_pct == 100:
            st.markdown(f"✅ :green[**{total_pct:.1f}%**]")
        else:
            st.markdown(f"⚠️ **{total_pct:.1f}%**")

    # Save button
    if total_pct > 100:
        st.error("總配置比例超過 100%，請調整後再儲存。")
        st.button("💾 儲存配置設定", disabled=True, use_container_width=True)
    else:
        if st.button("💾 儲存配置設定", type="primary", use_container_width=True):
            st.session_state.allocation_targets = new_targets
            save_all_data(
                st.session_state.accounts, 
                st.session_state.portfolio, 
                st.session_state.allocation_targets, 
                st.session_state.history_data,
                st.session_state.get("loan_plans", [])
            )
            st.success("設定已儲存")
            st.rerun()


def render_settings():
    """
    Main entry point for Settings & Configuration page.
    """
    st.title("⚙️ 管理設定")
    st.caption("設定帳戶資訊與投資配置目標")
    
    # Use tabs to organize settings
    tab1, tab2 = st.tabs(["🏦 帳戶管理", "🎯 配置設定"])
    
    with tab1:
        render_account_manager()
    
    with tab2:
        render_allocation_section()