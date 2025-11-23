"""
Custom exceptions for the Investment Dashboard.

This module defines custom exception classes for better error handling
and more informative error messages.
"""


class DashboardError(Exception):
    """Base exception for all dashboard-related errors."""
    
    def __init__(self, message: str, details: str = None):
        self.message = message
        self.details = details
        super().__init__(self.message)
    
    def __str__(self):
        if self.details:
            return f"{self.message}\nDetails: {self.details}"
        return self.message


class ConfigurationError(DashboardError):
    """Raised when there's a configuration error."""
    pass


class AuthenticationError(DashboardError):
    """Raised when authentication fails."""
    pass


class DriveServiceError(DashboardError):
    """Raised when Google Drive operations fail."""
    pass


class MarketDataError(DashboardError):
    """Raised when market data retrieval fails."""
    pass


class DataValidationError(DashboardError):
    """Raised when data validation fails."""
    pass


class EncryptionError(DashboardError):
    """Raised when encryption/decryption fails."""
    pass
