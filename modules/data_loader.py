"""
Data loader module for portfolio and settings management.

This module handles loading and saving portfolio data and allocation settings
from Google Drive with proper type safety and error handling.
"""

import streamlit as st
import pandas as pd
from typing import List, Dict, Optional
from googleapiclient.discovery import Resource

from modules.drive_manager import (
    get_drive_service,
    read_csv_from_drive,
    save_csv_to_drive,
    read_json_from_drive,
    save_json_to_drive,
    read_excel_from_drive,
    save_excel_to_drive,
)
from modules.logger import get_logger
from modules.exceptions import DriveServiceError, DataValidationError
from models import Asset, AllocationSettings, Account
from config import get_config

logger = get_logger(__name__)
config = get_config()


def get_service() -> Optional[Resource]:
    """
    Get Drive Service from Session State.
    
    Returns:
        Optional[Resource]: Google Drive service instance or None if not authenticated
    """
    if "google_creds" in st.session_state and st.session_state.google_creds:
        try:
            return get_drive_service(st.session_state.google_creds)
        except Exception as e:
            logger.error(f"Failed to get Drive service: {e}")
            return None
    return None


def load_portfolio() -> List[dict]:
    """
    Load portfolio from Google Drive.
    Supports legacy CSV if Excel not found.
    
    Returns:
        List[dict]: List of asset dictionaries
        
    Raises:
        DriveServiceError: If Drive service is unavailable or read fails
    """
    service = get_service()
    if not service:
        logger.warning("No Drive service available, returning empty portfolio")
        return []

    try:
        # Try loading Excel first
        data = read_excel_from_drive(service, config.google_drive.portfolio_filename)
        
        # If no Excel, try legacy CSV
        if not data:
            logger.info("Excel portfolio not found, checking legacy CSV")
            data = read_csv_from_drive(service, config.google_drive.legacy_portfolio_filename)

            # If found legacy data, we should probably save it as Excel to migrate
            if data:
                logger.info("Found legacy CSV portfolio, migrating to Excel")
                try:
                    save_excel_to_drive(service, config.google_drive.portfolio_filename, data)
                except Exception as ex:
                    logger.warning(f"Migration to Excel failed: {ex}")

        if not data:
            logger.info("No portfolio data found in Drive")
            return []
        
        # Data normalization - ensure all required fields exist
        normalized_data = []
        for item in data:
            # Fill in missing fields with defaults
            if "Manual_Price" not in item or pd.isna(item["Manual_Price"]):
                item["Manual_Price"] = 0.0
            if "Last_Update" not in item or pd.isna(item["Last_Update"]):
                item["Last_Update"] = "N/A"
            
            # Validate using Asset model
            try:
                asset = Asset.from_dict(item)
                # Migration: Assign default account if missing
                if not asset.account_id:
                    asset.account_id = "default_main"
                
                normalized_data.append(asset.to_dict())
            except Exception as e:
                logger.warning(f"Skipping invalid asset {item.get('Ticker', 'unknown')}: {e}")
                continue
        
        logger.info(f"Loaded {len(normalized_data)} assets from portfolio")
        return normalized_data
        
    except Exception as e:
        logger.error(f"Failed to load portfolio: {e}")
        raise DriveServiceError(
            "Failed to load portfolio from Google Drive",
            details=str(e)
        )


def save_portfolio(portfolio: List[dict]) -> None:
    """
    Save portfolio to Google Drive or local file (dev mode).
    
    Args:
        portfolio: List of asset dictionaries
        
    Raises:
        DriveServiceError: If Drive service is unavailable or save fails
        DataValidationError: If portfolio data is invalid
    """
    # Validate all assets before saving
    validated_portfolio = []
    for item in portfolio:
        try:
            asset = Asset.from_dict(item)
            validated_portfolio.append(asset.to_dict())
        except Exception as e:
            logger.error(f"Invalid asset data: {item}, error: {e}")
            raise DataValidationError(
                f"Invalid asset data for {item.get('Ticker', 'unknown')}",
                details=str(e)
            )
    
    # Check if in dev mode
    if config.dev_mode:
        import os
        xl_path = config.google_drive.portfolio_filename
        csv_path = config.google_drive.legacy_portfolio_filename # Ensure this maps to "my_portfolio.csv" or explicit string
        
        try:
            df = pd.DataFrame(validated_portfolio)
            
            # If my_portfolio.xlsx exists, save to CSV to avoid overwrite
            if os.path.exists(xl_path):
                # We could save to csv fallback
                config_csv_name = getattr(config.google_drive, "legacy_portfolio_filename", "my_portfolio.csv")
                df.to_csv(config_csv_name, index=False)
                logger.info(f"DEV_MODE: Excel file exists, saved {len(validated_portfolio)} assets to {config_csv_name}")
            else:
                # If no Excel file, create it
                df.to_excel(xl_path, index=False)
                logger.info(f"DEV_MODE: Created {xl_path} with {len(validated_portfolio)} assets")
            return
        except Exception as e:
            logger.error(f"Failed to save portfolio to local file: {e}")
            raise DriveServiceError(
                "Failed to save portfolio to local file",
                details=str(e)
            )
    
    # Production mode: save to Google Drive
    service = get_service()
    if not service:
        logger.error("Cannot save portfolio: No Drive service available")
        raise DriveServiceError("Drive service not available")
    
    try:
        save_excel_to_drive(service, config.google_drive.portfolio_filename, validated_portfolio)
        logger.info(f"Saved {len(validated_portfolio)} assets to portfolio (Excel)")
        
    except Exception as e:
        logger.error(f"Failed to save portfolio: {e}")
        raise DriveServiceError(
            "Failed to save portfolio to Google Drive",
            details=str(e)
        )


def load_allocation_settings() -> Dict[str, float]:
    """
    Load allocation settings from Google Drive.
    
    Returns:
        Dict[str, float]: Allocation targets by asset type
    """
    service = get_service()
    if not service:
        logger.warning("No Drive service, using default allocation settings")
        return config.allocation.targets.copy()

    try:
        # Try loading Excel
        excel_data = read_excel_from_drive(service, config.google_drive.settings_filename)
        data = {}
        
        if excel_data:
            # Convert Excel list of dicts back to simple dict
            # Expecting columns "Type" and "Target" (or whatever was saved)
            # If migrating from JSON {key: val}, we save as rows: Type, Target
            for row in excel_data:
                if "Type" in row and "Target" in row:
                    data[row["Type"]] = float(row["Target"])
        else:
            logger.info("Excel settings not found, checking legacy JSON")
            data = read_json_from_drive(service, config.google_drive.legacy_settings_filename)

            if data:
                # Migrate
                logger.info("Migrating settings to Excel")
                try:
                    # Transform dict to list for Excel
                    excel_list = [{"Type": k, "Target": v} for k, v in data.items()]
                    save_excel_to_drive(service, config.google_drive.settings_filename, excel_list)
                except Exception as ex:
                    logger.warning(f"Migration to Excel failed: {ex}")

        if not data:
            logger.info("No allocation settings found, using defaults")
            return config.allocation.targets.copy()
        
        # Validate using AllocationSettings model
        try:
            settings = AllocationSettings(targets=data)
            logger.info(f"Loaded allocation settings: {settings.targets}")
            return settings.to_dict()
        except Exception as e:
            logger.warning(f"Invalid allocation settings, using defaults: {e}")
            return config.allocation.targets.copy()
            
    except Exception as e:
        logger.error(f"Failed to load allocation settings: {e}")
        return config.allocation.targets.copy()


def save_allocation_settings(settings: Dict[str, float]) -> None:
    """
    Save allocation settings to Google Drive.
    
    Args:
        settings: Allocation targets by asset type
        
    Raises:
        DriveServiceError: If Drive service is unavailable or save fails
        DataValidationError: If settings are invalid
    """
    service = get_service()
    if not service:
        logger.error("Cannot save settings: No Drive service available")
        raise DriveServiceError("Drive service not available")
    
    try:
        # Validate settings
        allocation = AllocationSettings(targets=settings)
        
        if not allocation.is_valid():
            logger.warning(
                f"Allocation settings sum to {allocation.total_percentage()}%, not 100%"
            )
        
        # Convert dict to list for Excel
        excel_data = [{"Type": k, "Target": v} for k, v in allocation.to_dict().items()]
        save_excel_to_drive(service, config.google_drive.settings_filename, excel_data)
        logger.info("Saved allocation settings (Excel)")
        
    except Exception as e:
        logger.error(f"Failed to save allocation settings: {e}")
        raise DriveServiceError(
            "Failed to save allocation settings to Google Drive",
            details=str(e)
        )

def load_accounts() -> List[dict]:
    """
    Load accounts from Google Drive.
    If no accounts exist, creates a default one.
    
    Returns:
        List[dict]: List of account dictionaries
    """
    service = get_service()
    if not service:
        # Defaults for offline/dev mode or first run without drive
        return [Account(id="default_main", name="主要帳戶", type="投資帳戶", currency="TWD").to_dict()]

    try:
        # Try Excel
        data = read_excel_from_drive(service, config.google_drive.accounts_filename)
        
        if not data:
            # Try Legacy JSON
            logger.info("Excel accounts not found, checking legacy JSON")
            data = read_json_from_drive(service, config.google_drive.legacy_accounts_filename)

            if data:
                # Migrate
                logger.info("Migrating accounts to Excel")
                try:
                    save_excel_to_drive(service, config.google_drive.accounts_filename, data)
                except Exception as ex:
                    logger.warning(f"Migration to Excel failed: {ex}")

        if not data:
            logger.info("No accounts found, creating default")
            default_acc = Account(id="default_main", name="主要帳戶", type="投資帳戶", currency="TWD")
            accounts = [default_acc.to_dict()]
            save_excel_to_drive(service, config.google_drive.accounts_filename, accounts)
            return accounts
        
        # Validate keys
        valid_accounts = []
        for item in data:
            try:
                acc = Account.from_dict(item)
                valid_accounts.append(acc.to_dict())
            except Exception as e:
                logger.warning(f"Invalid account data: {item}, error: {e}")
        
        if not valid_accounts:
             # Fallback if file exists but is empty/invalid
            default_acc = Account(id="default_main", name="主要帳戶", type="投資帳戶", currency="TWD")
            valid_accounts = [default_acc.to_dict()]
            
        return valid_accounts
            
    except Exception as e:
        logger.error(f"Failed to load accounts: {e}")
        # Return default to allow app to function
        return [Account(id="default_main", name="主要帳戶", type="投資帳戶", currency="TWD").to_dict()]


def save_accounts(accounts: List[dict]) -> None:
    """
    Save accounts to Google Drive.
    
    Args:
        accounts: List of account dictionaries
    """
    service = get_service()
    if not service:
        logger.error("Cannot save accounts: No Drive service available")
        return # Or raise error
    
    try:
        # Validate
        validated = []
        for item in accounts:
            acc = Account.from_dict(item)
            validated.append(acc.to_dict())
            
        save_excel_to_drive(service, config.google_drive.accounts_filename, validated)
        logger.info(f"Saved {len(validated)} accounts (Excel)")
        
    except Exception as e:
        logger.error(f"Failed to save accounts: {e}")
        raise DriveServiceError("Failed to save accounts", details=str(e))
