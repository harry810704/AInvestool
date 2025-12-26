"""
Data loader module for portfolio, settings, and history management (v3.0).

This module handles loading and saving all data to a single 'portfolio.xlsx' file
hosted on Google Drive or locally (Dev Mode).
Schema: 4 Sheets - Accounts, Assets, Settings, History.
"""

import streamlit as st
import pandas as pd
import io
import os
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
from googleapiclient.discovery import Resource

from modules.drive_manager import (
    get_drive_service,
    read_excel_from_drive,
    save_excel_to_drive,
    read_csv_from_drive, # For migration
    read_json_from_drive, # For migration
)
from modules.logger import get_logger
from modules.exceptions import DriveServiceError, DataValidationError
from models import Asset, AllocationSettings, Account, HistoryRecord
from config import get_config

logger = get_logger(__name__)
config = get_config()

# Configuration Constants
PORTFOLIO_FILENAME = "portfolio.xlsx" # The v3.0 single file
SHEET_ACCOUNTS = "Accounts"
SHEET_ASSETS = "Assets"
SHEET_SETTINGS = "Settings"
SHEET_HISTORY = "History"

def get_service() -> Optional[Resource]:
    """Get Drive Service from Session State."""
    if "google_creds" in st.session_state and st.session_state.google_creds:
        try:
            return get_drive_service(st.session_state.google_creds)
        except Exception as e:
            logger.error(f"Failed to get Drive service: {e}")
            return None
    return None

def _migrate_legacy_data(service: Optional[Resource]) -> Dict[str, pd.DataFrame]:
    """
    Attempt to load data from legacy files (v2.0) and structure it for v3.0.
    Returns a dict of DataFrames {SheetName: DataFrame}.
    """
    logger.info("Starting migration from legacy files...")
    data_sheets = {}
    
    # 1. Accounts
    acc_data = []
    try:
        if service:
            raw_acc = read_excel_from_drive(service, config.google_drive.accounts_filename)
        elif config.dev_mode and os.path.exists(config.google_drive.accounts_filename):
            raw_acc = pd.read_excel(config.google_drive.accounts_filename).to_dict('records')
        else:
            raw_acc = []
            
        if raw_acc:
             for item in raw_acc:
                 try:
                     acc_data.append(Account.from_dict(item).to_dict())
                 except: pass
    except Exception as e:
        logger.warning(f"Failed to migrate accounts: {e}")
    
    if not acc_data:
        # Default Account
        acc_data = [Account(id="default_main", name="主要帳戶", type="投資帳戶", currency="TWD").to_dict()]
    data_sheets[SHEET_ACCOUNTS] = pd.DataFrame(acc_data)

    # 2. Assets
    asset_data = []
    try:
        # Try both xlsx and csv legacy names
        raw_assets = []
        if service:
             raw_assets = read_excel_from_drive(service, config.google_drive.portfolio_filename)
             if not raw_assets:
                 raw_assets = read_csv_from_drive(service, config.google_drive.legacy_portfolio_filename)
        elif config.dev_mode:
            if os.path.exists(config.google_drive.portfolio_filename):
                raw_assets = pd.read_excel(config.google_drive.portfolio_filename).to_dict('records')
            elif os.path.exists(config.google_drive.legacy_portfolio_filename):
                 raw_assets = pd.read_csv(config.google_drive.legacy_portfolio_filename).to_dict('records')

        if raw_assets:
            for i, item in enumerate(raw_assets):
                try:
                    # Enforce ID generation if missing
                    if "asset_id" not in item:
                        item["asset_id"] = f"ast_{i:03d}"
                    asset_data.append(Asset.from_dict(item).to_dict())
                except: pass
    except Exception as e:
         logger.warning(f"Failed to migrate assets: {e}")
    data_sheets[SHEET_ASSETS] = pd.DataFrame(asset_data)

    # 3. Settings
    settings_data = []
    try:
        raw_settings = []
        if service:
             raw_settings = read_excel_from_drive(service, config.google_drive.settings_filename)
        elif config.dev_mode and os.path.exists(config.google_drive.settings_filename):
             raw_settings = pd.read_excel(config.google_drive.settings_filename).to_dict('records')
        
        if raw_settings:
            # Assume row format: Type, Target
            settings_data = raw_settings
        else:
            # Default
            settings_data = [{"Type": k, "Target": v} for k, v in config.allocation.targets.items()]
    except Exception as e:
        logger.warning(f"Failed to migrate settings: {e}")
        settings_data = [{"Type": k, "Target": v} for k, v in config.allocation.targets.items()]
    
    # Rename columns to match v3 schema (Type -> asset_class, Target -> target_percentage)
    df_set = pd.DataFrame(settings_data)
    if not df_set.empty:
        df_set.rename(columns={"Type": "asset_class", "Target": "target_percentage"}, inplace=True)
    data_sheets[SHEET_SETTINGS] = df_set

    # 4. History (Empty for new)
    data_sheets[SHEET_HISTORY] = pd.DataFrame(columns=[
        "date", "total_net_worth_twd", "total_net_worth_usd", 
        "us_stock_val", "tw_stock_val", "cash_val", "crypto_val", "loan_val"
    ])
    
    return data_sheets

def load_all_data() -> Tuple[List[dict], List[dict], Dict[str, float], List[dict]]:
    """
    Load all data components from 'portfolio.xlsx'.
    
    Returns:
        Tuple: (accounts, assets, allocation_settings, history)
        - accounts: List[dict]
        - assets: List[dict]
        - allocation_settings: Dict[str, float]
        - history: List[dict]
    """
    service = get_service()
    
    # 1. Try to read the consolidated file
    dfs = {}
    try:
        if config.dev_mode:
            if os.path.exists(PORTFOLIO_FILENAME):
                dfs = pd.read_excel(PORTFOLIO_FILENAME, sheet_name=None)
                logger.info("DEV_MODE: Loaded portfolio.xlsx")
        elif service:
            # Need a helper to read all sheets. 
            # read_excel_from_drive returns list[dict] of the FIRST sheet usually or specified?
            # Existing `read_excel_from_drive` uses pd.read_excel(BytesIO(content)).
            # If we call it, it returns valid JSON-like list. But we want dict of DFs.
            # We need to access the raw bytes or modify drive_manager. 
            # Re-implementing specific download logic here for multi-sheet support.
            
            # Using private functionality or assuming we can get the file content.
            # Ideally modules/drive_manager.py should expose a `download_file_bytes` function.
            # For now, we reuse the logic: search file -> get_media -> BytesIO -> pd.read_excel(..., sheet_name=None)
            
            from modules.drive_manager import _get_file_id
            from googleapiclient.http import MediaIoBaseDownload
            
            file_id = _get_file_id(service, PORTFOLIO_FILENAME, config.google_drive.folder_name)
            if file_id:
                request = service.files().get_media(fileId=file_id)
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                fh.seek(0)
                dfs = pd.read_excel(fh, sheet_name=None)
                logger.info(f"Loaded portfolio.xlsx from Drive (ID: {file_id})")
            
    except Exception as e:
        logger.warning(f"Failed to load portfolio.xlsx: {e}")

    # 2. If load failed or file missing, perform migration
    if not dfs:
        dfs = _migrate_legacy_data(service)
        # Auto-save immediately to upgrade
        save_all_data(
            dfs[SHEET_ACCOUNTS].to_dict('records'),
            dfs[SHEET_ASSETS].to_dict('records'),
            _parse_settings(dfs[SHEET_SETTINGS].to_dict('records')),
            dfs[SHEET_HISTORY].to_dict('records')
        )
    
    # 3. Parse DataFrames into Models
    
    # Accounts
    accounts = []
    if SHEET_ACCOUNTS in dfs and not dfs[SHEET_ACCOUNTS].empty:
        for item in dfs[SHEET_ACCOUNTS].to_dict('records'):
            try:
                accounts.append(Account.from_dict(item).to_dict())
            except Exception as e: logger.warning(f"Invalid account: {e}")

    # Assets
    assets = []
    if SHEET_ASSETS in dfs and not dfs[SHEET_ASSETS].empty:
        for item in dfs[SHEET_ASSETS].to_dict('records'):
            try:
                assets.append(Asset.from_dict(item).to_dict())
            except Exception as e: logger.warning(f"Invalid asset: {e}")

    # Settings
    settings_dict = {}
    if SHEET_SETTINGS in dfs and not dfs[SHEET_SETTINGS].empty:
        settings_dict = _parse_settings(dfs[SHEET_SETTINGS].to_dict('records'))
    else:
        settings_dict = config.allocation.targets.copy()

    # History
    history = []
    if SHEET_HISTORY in dfs and not dfs[SHEET_HISTORY].empty:
        # Pre-process dates?
        history = dfs[SHEET_HISTORY].to_dict('records')
        # Validate?
        valid_hist = []
        for h in history:
            try:
                valid_hist.append(HistoryRecord.from_dict(h).to_dict())
            except: pass
        history = valid_hist

    return accounts, assets, settings_dict, history

def _parse_settings(records: List[dict]) -> Dict[str, float]:
    """Helper to parse settings sheet records to dict."""
    data = {}
    for row in records:
        # Support both new and legacy column names just in case
        cls = row.get("asset_class") or row.get("Type")
        pct = row.get("target_percentage") or row.get("Target")
        if cls and pct is not None:
             data[cls] = float(pct)
    return data

def save_all_data(
    accounts: List[dict], 
    assets: List[dict], 
    settings: Dict[str, float], 
    history: List[dict]
) -> None:
    """
    Save all data components to 'portfolio.xlsx'.
    
    Args:
        accounts: List[dict]
        assets: List[dict]
        settings: Dict[str, float]
        history: List[dict]
    """
    # 1. Prepare DataFrames
    
    # Accounts
    df_acc = pd.DataFrame([Account.from_dict(a).to_dict() for a in accounts])
    
    # Assets
    df_ast = pd.DataFrame([Asset.from_dict(a).to_dict() for a in assets])
    
    # Settings (Convert dict back to list)
    settings_list = [{"asset_class": k, "target_percentage": v} for k, v in settings.items()]
    df_set = pd.DataFrame(settings_list)
    
    # History
    df_hist = pd.DataFrame([HistoryRecord.from_dict(h).to_dict() for h in history])
    
    # 2. Write to Excel Bytes
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_acc.to_excel(writer, sheet_name=SHEET_ACCOUNTS, index=False)
        df_ast.to_excel(writer, sheet_name=SHEET_ASSETS, index=False)
        df_set.to_excel(writer, sheet_name=SHEET_SETTINGS, index=False)
        df_hist.to_excel(writer, sheet_name=SHEET_HISTORY, index=False)
    
    output.seek(0)
    
    # 3. Save (Local or Drive)
    if config.dev_mode:
        with open(PORTFOLIO_FILENAME, "wb") as f:
            f.write(output.getvalue())
        logger.info(f"DEV_MODE: Saved {PORTFOLIO_FILENAME}")
    else:
        service = get_service()
        if not service:
            raise DriveServiceError("No Drive service available")
        
        from modules.drive_manager import upload_file_stream
        upload_file_stream(
            service, 
            output, 
            PORTFOLIO_FILENAME, 
            config.google_drive.folder_name,
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        logger.info(f"Saved {PORTFOLIO_FILENAME} to Google Drive")

def save_snapshot(
    total_twd: float, 
    total_usd: float, 
    breakdown: Dict[str, float]
) -> None:
    """
    Create a new snapshot and save it to the history.
    
    Args:
        total_twd: Total Net Worth in TWD
        total_usd: Total Net Worth in USD
        breakdown: Dictionary of value by asset class (TWD usually, or base curr)
    """
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Load current history (from session state usually freshest)
    current_history = st.session_state.get("history_data", [])
    
    # 2. Create new record
    new_record = HistoryRecord(
        date=today,
        total_net_worth_twd=total_twd,
        total_net_worth_usd=total_usd,
        us_stock_val=breakdown.get("美股", 0),
        tw_stock_val=breakdown.get("台股", 0),
        cash_val=breakdown.get("現金", 0),
        crypto_val=breakdown.get("虛擬貨幣", 0),
        loan_val=breakdown.get("負債", 0)
    )
    
    # 3. Update logic: Overwrite if today exists, else append
    updated_history = []
    found = False
    for rec in current_history:
        if rec.get("date") == today:
            updated_history.append(new_record.to_dict())
            found = True
        else:
            updated_history.append(rec)
    
    if not found:
        updated_history.append(new_record.to_dict())
        
    # Sort by date
    updated_history.sort(key=lambda x: x["date"])
    
    # 4. Save Everything
    # Need full state
    accounts = st.session_state.get("accounts", [])
    portfolio = st.session_state.get("portfolio", [])
    allocation = st.session_state.get("allocation_targets", {})
    
    # Update session state first
    st.session_state.history_data = updated_history
    
    save_all_data(accounts, portfolio, allocation, updated_history)
    logger.info(f"Snapshot saved for {today}")

