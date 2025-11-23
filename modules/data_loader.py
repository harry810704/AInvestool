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
)
from modules.logger import get_logger
from modules.exceptions import DriveServiceError, DataValidationError
from models import Asset, AllocationSettings
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
        data = read_csv_from_drive(service, config.google_drive.portfolio_filename)
        
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
    Save portfolio to Google Drive.
    
    Args:
        portfolio: List of asset dictionaries
        
    Raises:
        DriveServiceError: If Drive service is unavailable or save fails
        DataValidationError: If portfolio data is invalid
    """
    service = get_service()
    if not service:
        logger.error("Cannot save portfolio: No Drive service available")
        raise DriveServiceError("Drive service not available")
    
    try:
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
        
        save_csv_to_drive(service, config.google_drive.portfolio_filename, validated_portfolio)
        logger.info(f"Saved {len(validated_portfolio)} assets to portfolio")
        
    except DataValidationError:
        raise
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
        data = read_json_from_drive(service, config.google_drive.settings_filename)
        
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
        
        save_json_to_drive(service, config.google_drive.settings_filename, allocation.to_dict())
        logger.info("Saved allocation settings")
        
    except Exception as e:
        logger.error(f"Failed to save allocation settings: {e}")
        raise DriveServiceError(
            "Failed to save allocation settings to Google Drive",
            details=str(e)
        )
