"""
Main application entry point for the Investment Dashboard.

This is a Streamlit-based portfolio management application with
Google Drive integration for data persistence.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import extra_streamlit_components as stx

from modules.security import encrypt_token_data, decrypt_token_data
from modules.drive_manager import (
    get_login_url,
    exchange_code_for_token,
    credentials_to_dict,
    credentials_from_dict,
    get_user_info,
)
from modules.data_loader import load_portfolio, save_portfolio, load_allocation_settings
from modules.market_service import (
    get_exchange_rate,
    get_market_data,
    auto_update_portfolio,
)
from modules.ui_dashboard import render_dashboard
from modules.ui_manager import render_manager
from modules.state_manager import get_state_manager
from modules.logger import get_logger
from config import get_config

# Initialize configuration and logger
config = get_config()
logger = get_logger(__name__)
state = get_state_manager()

# Page configuration
st.set_page_config(
    page_title=config.ui.page_title,
    layout=config.ui.layout,
    page_icon=config.ui.page_icon
)

logger.info("Application started")

# Initialize Cookie Manager
cookie_manager = stx.CookieManager()

# ==========================================
# Authentication Flow
# ==========================================

def restore_session_from_cookie() -> None:
    """Attempt to restore session from encrypted cookie."""
    if state.is_authenticated:
        return
    
    encrypted_cookie = cookie_manager.get(cookie=config.security.cookie_name)
    
    if encrypted_cookie:
        logger.debug("Found encrypted cookie, attempting to restore session")
        token_dict = decrypt_token_data(encrypted_cookie)
        
        if token_dict:
            creds, was_refreshed = credentials_from_dict(token_dict)
            
            if creds:
                state.google_creds = creds
                logger.info("Session restored from cookie")
                
                # Get user info
                user_info = get_user_info(creds)
                if user_info:
                    state.user_info = user_info
                
                # Update cookie if token was refreshed
                if was_refreshed:
                    logger.info("Token was refreshed, updating cookie")
                    new_encrypted = encrypt_token_data(credentials_to_dict(creds))
                    cookie_manager.set(
                        config.security.cookie_name,
                        new_encrypted,
                        key="refresh_set",
                        expires_at=datetime.now() + timedelta(days=config.security.cookie_expiry_days),
                    )
            else:
                logger.warning("Invalid credentials in cookie, deleting")
                cookie_manager.delete(config.security.cookie_name)
        else:
            logger.warning("Failed to decrypt cookie, deleting")
            cookie_manager.delete(config.security.cookie_name)


def handle_oauth_callback() -> None:
    """Handle OAuth callback with authorization code."""
    if "code" not in st.query_params:
        return
    
    code = st.query_params["code"]
    logger.info("Processing OAuth callback")
    
    creds = exchange_code_for_token(code)
    if creds:
        state.google_creds = creds
        logger.info("OAuth authentication successful")
        
        # Get user info
        user_info = get_user_info(creds)
        if user_info:
            state.user_info = user_info
            logger.info(f"User info retrieved: {user_info['email']}")
        
        # Encrypt and store in cookie
        token_dict = credentials_to_dict(creds)
        encrypted_token = encrypt_token_data(token_dict)
        
        if encrypted_token:
            cookie_manager.set(
                config.security.cookie_name,
                encrypted_token,
                key="login_set",
                expires_at=datetime.now() + timedelta(days=config.security.cookie_expiry_days),
            )
            logger.info("Credentials saved to encrypted cookie")
        
        st.query_params.clear()
        st.rerun()
    else:
        logger.error("OAuth authentication failed")


def render_login_page() -> None:
    """Render the login page."""
    st.title(f"☁️ {config.ui.page_title}")
    st.write("請先登入 Google 帳號以讀取您的投資組合。")
    
    login_url = get_login_url()
    st.link_button("🔑 使用 Google 帳號登入", login_url, type="primary")
    
    st.divider()
    st.caption(
        f"🔒 安全提示：您的登入憑證將經過 AES-128 加密後儲存於瀏覽器 Cookie 中，"
        f"有效期 {config.security.cookie_expiry_days} 天。"
    )


def handle_logout() -> None:
    """Handle user logout."""
    logger.info("User logging out")
    
    # Delete the encrypted cookie
    cookie_manager.delete(config.security.cookie_name)
    
    # Clear ALL session state (not just managed keys)
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    
    st.rerun()


# ==========================================
# Main Application Logic
# ==========================================

# Restore session from cookie if available
restore_session_from_cookie()

# Handle OAuth callback
handle_oauth_callback()

# Check authentication
if not state.is_authenticated:
    render_login_page()
    st.stop()

logger.debug("User is authenticated, loading application")

# Initialize session state
state.initialize()

# Load portfolio data
if not state.load_portfolio and not state.portfolio: # Changed from "portfolio" not in st.session_state
    logger.info("Loading portfolio from Google Drive")
    with st.spinner("正在從 Google Drive 同步資料..."):
        portfolio = load_portfolio()
        logger.info("Loading allocation settings")
        state.allocation_targets = load_allocation_settings()
        if not portfolio:
            logger.info("No portfolio found, creating default")
            portfolio = [{
                "Type": "美股",
                "Ticker": "AAPL",
                "Quantity": 10,
                "Avg_Cost": 150.0,
                "Currency": "USD",
                "Manual_Price": 0.0,
                "Last_Update": "N/A",
            }]
            save_portfolio(portfolio)
        state.portfolio = portfolio
    state.load_portfolio = True

# Sidebar
with st.sidebar:
    st.success("已連線 ✅")
    
    # Display user info
    if state.user_info:
        st.markdown(f"**👤 {state.user_info.get('name', 'User')}**")
        st.caption(state.user_info.get('email', ''))
    
    if st.button("🚪 登出", use_container_width=True):
        handle_logout()

# Auto-update portfolio prices
if state.portfolio and not state.has_auto_updated: # Changed from 'portfolio' in st.session_state and "has_auto_updated" not in st.session_state
    logger.info("Starting automatic portfolio update")
    with st.status("🔄 正在檢查並更新資產價格...", expanded=True) as status:
        success, fail, updated_portfolio = auto_update_portfolio(state.portfolio)
        state.portfolio = updated_portfolio
        
        if success > 0:
            save_portfolio(state.portfolio)
            logger.info(f"Portfolio updated: {success} success, {fail} failed")
        
        if fail > 0:
            status.update(
                label=f"更新完成: {success} 成功, {fail} 失敗",
                state="error",
                expanded=False,
            )
        elif success > 0:
            status.update(
                label=f"更新完成: {success} 筆資產已同步",
                state="complete",
                expanded=False,
            )
        else:
            status.update(
                label="資產價格皆為最新",
                state="complete",
                expanded=False
            )
    state.has_auto_updated = True

# Main UI
current_usd_twd = get_exchange_rate()
logger.debug(f"Current exchange rate: 1 USD = {current_usd_twd:.2f} TWD")

with st.sidebar:
    st.header("⚙️ 全域設定")
    st.write(f"匯率參考: 1 USD ≈ {current_usd_twd:.2f} TWD")
    display_currency = st.radio(
        "顯示幣別",
        ["TWD (新台幣)", "USD (美金)"],
        horizontal=True
    )
    st.divider()

target_curr_code = "TWD" if "TWD" in display_currency else "USD"
c_symbol = config.ui.currency_symbols.get(target_curr_code, "$")

# Get market data - only fetch on initial load or when explicitly requested
# Check if we need to fetch market data
need_fetch = False
if "market_data_fetched" not in st.session_state:
    need_fetch = True
    st.session_state["market_data_fetched"] = True
elif "force_refresh_market_data" in st.session_state and st.session_state["force_refresh_market_data"]:
    need_fetch = True
    st.session_state["force_refresh_market_data"] = False

if need_fetch:
    logger.info("Fetching market data")
    if state.portfolio:
        df_all = get_market_data(state.portfolio, target_curr_code, current_usd_twd)
        total_val = df_all["Market_Value"].sum() if not df_all.empty else 0
    else:
        df_all = pd.DataFrame()
        total_val = 0
    
    # Cache the results
    st.session_state["last_market_data"] = df_all
    st.session_state["last_total_val"] = total_val
    st.session_state["last_currency"] = target_curr_code
else:
    # Use cached data, but recalculate if currency changed
    if "last_currency" in st.session_state and st.session_state["last_currency"] != target_curr_code:
        logger.info("Currency changed, refetching market data")
        if state.portfolio:
            df_all = get_market_data(state.portfolio, target_curr_code, current_usd_twd)
            total_val = df_all["Market_Value"].sum() if not df_all.empty else 0
        else:
            df_all = pd.DataFrame()
            total_val = 0
        st.session_state["last_market_data"] = df_all
        st.session_state["last_total_val"] = total_val
        st.session_state["last_currency"] = target_curr_code
    else:
        # Use cached data
        df_all = st.session_state.get("last_market_data", pd.DataFrame())
        total_val = st.session_state.get("last_total_val", 0)

# Render tabs
tab1, tab2 = st.tabs(["📊 投資戰情室", "⚙️ 設定與管理"])

with tab1:
    render_dashboard(df_all, c_symbol, total_val)

with tab2:
    render_manager(df_all, c_symbol, total_val)

logger.debug("Application render complete")
