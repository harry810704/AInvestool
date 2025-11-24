"""
Session state management for the Investment Dashboard.

This module provides centralized, type-safe access to Streamlit session state
with default value management and validation.
"""

import streamlit as st
from typing import Optional, List, Any
from google.oauth2.credentials import Credentials

from models import Asset, AllocationSettings
from config import get_config


class SessionStateManager:
    """
    Manages Streamlit session state with type safety and defaults.
    
    This class provides a clean interface for accessing and modifying
    session state, ensuring consistency and reducing bugs.
    """
    
    # State keys
    GOOGLE_CREDS = "google_creds"
    USER_INFO = "user_info"
    PORTFOLIO = "portfolio"
    ALLOCATION_TARGETS = "allocation_targets"
    HAS_AUTO_UPDATED = "has_auto_updated"
    DRAFT_ACTIONS = "draft_actions"
    CALC_BASE_SUGGESTIONS = "calc_base_suggestions"
    CALC_MANUAL_ADJUST = "calc_manual_adjust"
    LAST_CALC_FUND = "last_calc_fund"
    LOAD_PORTFOLIO = "load_portfolio"
    LOAD_ALLOCATION_TARGETS = "load_allocation_targets"
    
    def __init__(self):
        """Initialize the state manager."""
        self.config = get_config()
    
    # Google Credentials
    
    @property
    def google_creds(self) -> Optional[Credentials]:
        """Get Google credentials from session state."""
        return st.session_state.get(self.GOOGLE_CREDS)
    
    @google_creds.setter
    def google_creds(self, value: Optional[Credentials]):
        """Set Google credentials in session state."""
        st.session_state[self.GOOGLE_CREDS] = value
    
    def clear_google_creds(self):
        """Clear Google credentials from session state."""
        if self.GOOGLE_CREDS in st.session_state:
            del st.session_state[self.GOOGLE_CREDS]
    
    @property
    def user_info(self) -> Optional[dict]:
        """Get user information from session state."""
        return st.session_state.get(self.USER_INFO)
    
    @user_info.setter
    def user_info(self, value: Optional[dict]):
        """Set user information in session state."""
        st.session_state[self.USER_INFO] = value
    
    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self.google_creds is not None
    
    # Portfolio
    
    @property
    def portfolio(self) -> List[dict]:
        """
        Get portfolio from session state.
        
        Returns:
            List[dict]: List of asset dictionaries
        """
        if self.PORTFOLIO not in st.session_state:
            st.session_state[self.PORTFOLIO] = []
        return st.session_state[self.PORTFOLIO]
    
    @portfolio.setter
    def portfolio(self, value: List[dict]):
        """Set portfolio in session state."""
        st.session_state[self.PORTFOLIO] = value
    
    def get_portfolio_assets(self) -> List[Asset]:
        """
        Get portfolio as validated Asset objects.
        
        Returns:
            List[Asset]: List of validated Asset instances
        """
        return [Asset.from_dict(item) for item in self.portfolio]
    
    def set_portfolio_assets(self, assets: List[Asset]):
        """
        Set portfolio from Asset objects.
        
        Args:
            assets: List of Asset instances
        """
        self.portfolio = [asset.to_dict() for asset in assets]
    
    def add_asset(self, asset: Asset):
        """
        Add an asset to the portfolio.
        
        Args:
            asset: Asset to add
        """
        portfolio = self.portfolio
        portfolio.append(asset.to_dict())
        self.portfolio = portfolio
    
    def remove_asset(self, index: int):
        """
        Remove an asset from the portfolio by index.
        
        Args:
            index: Index of asset to remove
        """
        portfolio = self.portfolio
        if 0 <= index < len(portfolio):
            portfolio.pop(index)
            self.portfolio = portfolio
    
    def update_asset(self, index: int, asset: Asset):
        """
        Update an asset in the portfolio.
        
        Args:
            index: Index of asset to update
            asset: New asset data
        """
        portfolio = self.portfolio
        if 0 <= index < len(portfolio):
            portfolio[index] = asset.to_dict()
            self.portfolio = portfolio
    
    def clear_portfolio(self):
        """Clear all assets from portfolio."""
        self.portfolio = []
    
    # Allocation Targets
    
    @property
    def allocation_targets(self) -> dict:
        """
        Get allocation targets from session state.
        
        Returns:
            dict: Allocation targets by asset type
        """
        if self.ALLOCATION_TARGETS not in st.session_state:
            st.session_state[self.ALLOCATION_TARGETS] = self.config.allocation.targets.copy()
        return st.session_state[self.ALLOCATION_TARGETS]
    
    @allocation_targets.setter
    def allocation_targets(self, value: dict):
        """Set allocation targets in session state."""
        st.session_state[self.ALLOCATION_TARGETS] = value
    
    def get_allocation_settings(self) -> AllocationSettings:
        """
        Get allocation settings as validated model.
        
        Returns:
            AllocationSettings: Validated allocation settings
        """
        return AllocationSettings(targets=self.allocation_targets)
    
    def set_allocation_settings(self, settings: AllocationSettings):
        """
        Set allocation settings from model.
        
        Args:
            settings: AllocationSettings instance
        """
        self.allocation_targets = settings.to_dict()
    
    # Auto Update Flag
    
    @property
    def has_auto_updated(self) -> bool:
        """Check if auto update has run this session."""
        return st.session_state.get(self.HAS_AUTO_UPDATED, False)
    
    @has_auto_updated.setter
    def has_auto_updated(self, value: bool):
        """Set auto update flag."""
        st.session_state[self.HAS_AUTO_UPDATED] = value
    
    # Load Flags
    
    @property
    def load_portfolio(self) -> bool:
        """Check if portfolio has been loaded this session."""
        return st.session_state.get(self.LOAD_PORTFOLIO, False)
    
    @load_portfolio.setter
    def load_portfolio(self, value: bool):
        """Set portfolio loaded flag."""
        st.session_state[self.LOAD_PORTFOLIO] = value
    
    @property
    def load_allocation_targets(self) -> bool:
        """Check if allocation targets have been loaded this session."""
        return st.session_state.get(self.LOAD_ALLOCATION_TARGETS, False)
    
    @load_allocation_targets.setter
    def load_allocation_targets(self, value: bool):
        """Set allocation targets loaded flag."""
        st.session_state[self.LOAD_ALLOCATION_TARGETS] = value
    
    # Draft Actions (for deployment planning)
    
    @property
    def draft_actions(self) -> List[dict]:
        """Get draft deployment actions."""
        if self.DRAFT_ACTIONS not in st.session_state:
            st.session_state[self.DRAFT_ACTIONS] = []
        return st.session_state[self.DRAFT_ACTIONS]
    
    @draft_actions.setter
    def draft_actions(self, value: List[dict]):
        """Set draft deployment actions."""
        st.session_state[self.DRAFT_ACTIONS] = value
    
    def clear_draft_actions(self):
        """Clear all draft actions."""
        self.draft_actions = []
    
    # Calculator State
    
    def get_calc_state(self, key: str, default: Any = None) -> Any:
        """
        Get calculator state value.
        
        Args:
            key: State key
            default: Default value if not found
            
        Returns:
            State value or default
        """
        return st.session_state.get(key, default)
    
    def set_calc_state(self, key: str, value: Any):
        """
        Set calculator state value.
        
        Args:
            key: State key
            value: Value to set
        """
        st.session_state[key] = value
    
    # General Utilities
    
    def clear_all(self):
        """Clear all managed session state (useful for logout)."""
        keys_to_clear = [
            self.GOOGLE_CREDS,
            self.USER_INFO,
            self.PORTFOLIO,
            self.ALLOCATION_TARGETS,
            self.HAS_AUTO_UPDATED,
            self.DRAFT_ACTIONS,
            self.CALC_BASE_SUGGESTIONS,
            self.CALC_MANUAL_ADJUST,
            self.LAST_CALC_FUND,
            self.LOAD_PORTFOLIO,
            self.LOAD_ALLOCATION_TARGETS,
        ]
        
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
    
    def initialize(self):
        """
        Initialize session state with defaults if needed.
        This should be called early in the app lifecycle.
        """
        # Ensure portfolio exists
        _ = self.portfolio
        
        # Ensure allocation targets exist
        _ = self.allocation_targets


# Global instance
_state_manager: Optional[SessionStateManager] = None


def get_state_manager() -> SessionStateManager:
    """
    Get the global session state manager instance.
    
    Returns:
        SessionStateManager: The state manager instance
    """
    global _state_manager
    if _state_manager is None:
        _state_manager = SessionStateManager()
    return _state_manager
