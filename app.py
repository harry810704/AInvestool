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
from modules.ui_tools import render_tools
from modules.state_manager import get_state_manager
from modules.logger import get_logger
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

# Inject Global Custom CSS - Dark Theme
st.markdown("""
<style>
    /* Card Styling - Dark Theme */
    div[data-testid="stMetric"], div.css-card {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border: 1px solid #475569;
        padding: 18px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        transition: all 0.3s ease;
        color: #f1f5f9;
    }
    div[data-testid="stMetric"]:hover, div.css-card:hover {
        box-shadow: 0 8px 20px rgba(0,0,0,0.4);
        transform: translateY(-2px);
        border-color: #64748b;
    }
    
    /* Metric labels - ensure visibility */
    div[data-testid="stMetric"] label {
        color: #cbd5e1 !important;
        font-weight: 600;
    }
    
    /* Metric values - ensure visibility */
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #f1f5f9 !important;
        font-weight: 700;
    }

    /* Table Styling - Dark Theme */
    div[data-testid="stDataFrame"] {
        border: 1px solid #475569;
        border-radius: 12px;
        padding: 8px;
        background-color: #1e293b;
    }

    /* Tabs - Dark Theme */
    .stTabs [data-baseweb="tab-list"] {
        gap: 20px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #1e293b;
        border-radius: 8px 8px 0 0;
        font-size: 16px;
        font-weight: 600;
        color: #94a3b8;
        border: 1px solid #334155;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #334155 0%, #475569 100%);
        border-bottom: 3px solid #60a5fa;
        color: #f1f5f9;
    }

    /* Button Styling - Enhanced */
    button[kind="primary"] {
        background: linear-gradient(135deg, #5D69B1 0%, #4A569D 100%);
        border-color: #5D69B1;
        color: white;
        font-weight: 600;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(93, 105, 177, 0.3);
        transition: all 0.3s ease;
    }
    button[kind="primary"]:hover {
        background: linear-gradient(135deg, #4A569D 0%, #3d4a82 100%);
        border-color: #4A569D;
        box-shadow: 0 4px 12px rgba(93, 105, 177, 0.5);
        transform: translateY(-1px);
    }
    
    /* General text colors for dark theme */
    .css-card div {
        color: #e2e8f0;
    }
</style>
""", unsafe_allow_html=True)



# ==========================================
# Main Application Logic
# ==========================================



# Load portfolio data
if not state.load_portfolio and not state.portfolio:
    if config.dev_mode:
        # In dev mode, check Excel first then CSV
        logger.info("DEV_MODE: Loading portfolio from local file")
        import os
        
        # We should really use data_loader logic even in dev mode to ensure consistency
        # But data_loader.load_portfolio is tied to Google Drive Service
        # For now, let's replicate the logic locally or patch it

        portfolio = []
        loaded = False

        # Custom Dev Mode Loader: Load newest of xlsx or csv
        xl_path = config.google_drive.portfolio_filename
        csv_path = config.google_drive.legacy_portfolio_filename # or "my_portfolio.csv"
        
        load_xlsx = False
        load_csv = False
        
        # Check existence
        has_xl = os.path.exists(xl_path)
        has_csv = os.path.exists(csv_path)
        
        target_file = None
        
        if has_xl and has_csv:
            # Compare modification time
            if os.path.getmtime(xl_path) >= os.path.getmtime(csv_path):
                target_file = "xlsx"
            else:
                target_file = "csv"
        elif has_xl:
            target_file = "xlsx"
        elif has_csv:
            target_file = "csv"
            
        # Load based on target
        if target_file == "xlsx":
            try:
                df = pd.read_excel(xl_path)
                portfolio = df.to_dict('records')
                loaded = True
                logger.info(f"Loaded {len(portfolio)} assets from local Excel ({xl_path})")
            except Exception as e:
                logger.error(f"Failed to load local Excel: {e}")
                # Fallback to csv if exists?
                if has_csv: target_file = "csv"

        if target_file == "csv" or (not loaded and has_csv):
            try:
                df = pd.read_csv(csv_path)
                portfolio = df.to_dict('records')
                loaded = True
                logger.info(f"Loaded {len(portfolio)} assets from local CSV ({csv_path})")
            except Exception as e:
                logger.error(f"Failed to load local CSV: {e}")

        if not loaded:
            logger.info("No local portfolio found, creating default")
            portfolio = [{
                "asset_class": "美股",
                "symbol": "AAPL",
                "quantity": 10,
                "avg_cost": 150.0,
                "currency": "USD",
                "manual_price": 0.0,
                "last_update": "N/A",
                "account_id": "default_main"
            }]
        
        # Normalize keys/data (important for dev mode to match prod behavior)
        # This handles missing Account_ID etc.
        from models import Asset
        normalized_portfolio = []
        for item in portfolio:
            try:
                asset = Asset.from_dict(item)
                if not asset.account_id:
                    asset.account_id = "default_main"
                normalized_portfolio.append(asset.to_dict())
            except Exception as e:
                logger.warning(f"Skipping invalid asset in dev mode: {e}")

        state.portfolio = normalized_portfolio

        # Load allocation settings from local file or use defaults
        state.allocation_targets = config.allocation.targets.copy()

        # Load local accounts if possible, else default
        st.session_state.accounts = load_accounts() # data_loader handles local fallback
    else:
        # Production mode: load from Google Drive
        logger.info("Loading portfolio from Google Drive")
        with st.spinner("正在從 Google Drive 同步資料..."):
            portfolio = load_portfolio()
            logger.info("Loading allocation settings")
            state.allocation_targets = load_allocation_settings()
            if not portfolio:
                logger.info("No portfolio found, creating default")
                portfolio = [{
                    "asset_class": "美股",
                    "symbol": "AAPL",
                    "quantity": 10,
                    "avg_cost": 150.0,
                    "currency": "USD",
                    "manual_price": 0.0,
                    "last_update": "N/A",
                    "account_id": "default_main"
                }]
                save_portfolio(portfolio)
            state.portfolio = portfolio
            
            # Load accounts
            logger.info("Loading accounts")
            st.session_state.accounts = load_accounts()
            
    state.load_portfolio = True
    # Force market data refresh when portfolio is loaded
    st.session_state["force_refresh_market_data"] = True

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


# Render tabs - NEW 4-TAB STRUCTURE
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 儀表板", 
    "💼 資產管理", 
    "⚙️ 管理設定", 
    "🛠️ 輔助工具"
])

with tab1:
    render_dashboard(df_all, c_symbol, total_val, current_usd_twd)

with tab2:
    render_asset_management(df_all, c_symbol)

with tab3:
    render_settings()

with tab4:
    render_tools(df_all, c_symbol, total_val, state.portfolio)

logger.debug("Application render complete")
