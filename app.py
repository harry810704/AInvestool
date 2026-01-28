"""
Main application entry point for the Investment Dashboard.

This is a Streamlit-based portfolio management application with
Google Drive integration for data persistence.
"""

import streamlit as st
# Trigger reload: Fixed import errors
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
from modules.data_loader import load_all_data, save_all_data
from modules.market_service import (
    get_exchange_rate,
    get_market_data,
    auto_update_portfolio,
)
from modules.ui_dashboard import render_dashboard
from modules.ui_asset_management import render_asset_management
from modules.ui_settings import render_settings
from modules.ui_analytics import render_analytics
from modules.state_manager import get_state_manager
from modules.logger import get_logger
from modules.style import apply_tech_theme
from config import get_config

# Initialize configuration and logger
config = get_config()
logger = get_logger(__name__)
state = get_state_manager()

# Page configuration - MUST be the first Streamlit command
st.set_page_config(
    page_title=config.ui.page_title,
    layout=config.ui.layout,
    page_icon=config.ui.page_icon
)

# State and Authentication must be handled BEFORE data loading
# Initialize session state (no UI output)
state.initialize()

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
    
    # Get the code and clear it immediately to prevent reuse
    code = st.query_params["code"]
    st.query_params.clear()
    
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
        else:
            logger.warning("Could not retrieve user info, but authentication succeeded")
        
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
        
        st.rerun()
    else:
        logger.error("OAuth authentication failed")
        st.error("認證失敗，請重試")


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

# Restore session from cookie if available (skip in dev mode)
if not config.dev_mode:
    restore_session_from_cookie()

# Handle OAuth callback (skip in dev mode)
if not config.dev_mode:
    handle_oauth_callback()

# Check authentication (allow dev mode to bypass)
if not config.dev_mode and not state.is_authenticated:
    render_login_page()
    st.stop()
    
# Dev mode authentication bypass
if config.dev_mode and not state.is_authenticated:
    logger.warning("DEV_MODE enabled - bypassing authentication with fake user")
    # Set fake credentials for dev mode
    state.user_info = {
        'email': 'dev_user@localhost',
        'name': 'Dev User',
        'picture': '',
        'sub': 'dev_user_id'
    }
    logger.info("Dev mode user set")

logger.debug("User authenticated or in dev mode, loading application")

# ==========================================
# Data Loading (After Auth)
# ==========================================
# Load ALL data (Portfolio, Accounts, Settings, History)
if not state.load_portfolio:
    if config.dev_mode:
        logger.info("DEV_MODE: Loading from local portfolio.xlsx")
    else:
        logger.info("Loading from Google Drive")
        
    with st.spinner("正在讀取資料..."):
        accounts, assets, settings, history, loan_plans = load_all_data()
        
        # If no assets found in dev mode, create default
        if not assets and config.dev_mode:
            logger.info("No local portfolio found, creating default")
            from models import Asset
            default_asset = {
                "category": "investment",
                "asset_type": "美股",
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "quantity": 10.0,
                "avg_cost": 150.0,
                "currency": "USD",
                "current_price": 175.0,
                "account_id": "default_main"
            }
            try:
                assets = [Asset.from_dict(default_asset).to_dict()]
                # Also save it so next time it's there
                save_all_data(accounts, assets, settings, history, loan_plans)
            except Exception as e:
                logger.error(f"Failed to create default asset: {e}")

        state.accounts = accounts
        state.portfolio = assets
        state.allocation_targets = settings
        state.history_data = history
        state.loan_plans = loan_plans
            
    state.load_portfolio = True
    # Force market data refresh when portfolio is loaded
    st.session_state["force_refresh_market_data"] = True

# Display data validation errors if any
if "data_validation_errors" in st.session_state and st.session_state.data_validation_errors:
    errors = st.session_state.data_validation_errors
    with st.expander(f"⚠️ 發現 {len(errors)} 筆資料問題，請修正 Excel 檔案", expanded=True):
        st.warning("以下資產資料有缺失或錯誤，已跳過載入。請修正 Excel 檔案後重新啟動應用程式。")
        
        for err in errors:
            st.error(f"""
            **Excel 第 {err['row']} 列**  
            **資產代號:** {err['symbol']}  
            **錯誤:** {err['error']}
            """)
        
        st.info("💡 **常見問題:**\n- 投資資產缺少 `account_id` (所屬帳戶)\n- 投資資產缺少 `symbol` (代號)\n- 投資資產缺少 `quantity` (持倉數量)")
    
    # Clear errors after display (only show once)
    del st.session_state.data_validation_errors

# Sidebar
with st.sidebar:
    if config.dev_mode:
        st.warning("🔧 DEV MODE")
        st.caption("開發模式：使用本地檔案")
    else:
        st.success("已連線 ✅")
    
    # Display user info
    if state.user_info:
        st.markdown(f"**👤 {state.user_info.get('name', 'User')}**")
        st.caption(state.user_info.get('email', ''))
    
    if not config.dev_mode:
        if st.button("🚪 登出", use_container_width=True):
            handle_logout()
    else:
        st.caption("開發模式下無需登出")

# Auto-update portfolio prices
if state.portfolio and not state.has_auto_updated: # Changed from 'portfolio' in st.session_state and "has_auto_updated" not in st.session_state
    logger.info("Starting automatic portfolio update")
    with st.status("🔄 正在檢查並更新資產價格...", expanded=True) as status:
        success, fail, updated_portfolio = auto_update_portfolio(state.portfolio)
        state.portfolio = updated_portfolio
        
        if success > 0:
            # Save ALL data
            save_all_data(state.accounts, state.portfolio, state.allocation_targets, state.history_data, state.loan_plans)
            st.session_state["force_refresh_market_data"] = True
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

logger.info("Application started")

# Inject Global Custom CSS - Tech Theme
apply_tech_theme()



# ==========================================
# Main Application Logic
# ==========================================

# Main UI
current_usd_twd = get_exchange_rate()
logger.debug(f"Current exchange rate: 1 USD = {current_usd_twd:.2f} TWD")

with st.sidebar:
    st.header("⚙️ 全域設定")
    st.write(f"匯率參考: 1 USD ≈ {current_usd_twd:.2f} TWD")
    display_currency = st.radio(
        "顯示幣別",
        config.ui.currencies, # ["Auto", "USD", "TWD"]
        horizontal=True,
        index=0
    )
    st.divider()

target_curr_code = display_currency.split()[0] if " " in display_currency else display_currency
# If Auto, symbol is mixed, but c_symbol usually passed to components for Total.
# If Auto, Total is TWD (Base).
c_symbol_key = target_curr_code if target_curr_code != "Auto" else "TWD"
c_symbol = config.ui.currency_symbols.get(c_symbol_key, "$")

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
        # Use Net_Value for Total (Net Worth)
        total_val = df_all["Net_Value"].sum() if not df_all.empty else 0
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
            total_val = df_all["Net_Value"].sum() if not df_all.empty else 0
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
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Dashboard",
    "💼 Assets",
    "📈 Analytics",
    "⚙️ Settings"
])

with tab1:
    render_dashboard(df_all, c_symbol, total_val, current_usd_twd)

with tab2:
    render_asset_management(df_all, c_symbol)

with tab3:
    render_analytics(df_all, c_symbol, total_val, state.portfolio)

with tab4:
    render_settings()

logger.debug("Application render complete")
