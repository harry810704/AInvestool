"""
Security module for encryption and token management.

This module provides encryption/decryption utilities for securing
sensitive data like authentication tokens.
"""

import streamlit as st
import json
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet, InvalidToken

from modules.logger import get_logger
from modules.exceptions import EncryptionError, ConfigurationError
from config import get_config

logger = get_logger(__name__)
config = get_config()


def get_fernet() -> Fernet:
    """
    Get Fernet cipher instance from secrets.
    
    Returns:
        Fernet: Configured Fernet cipher
        
    Raises:
        ConfigurationError: If encryption key is not configured
    """
    try:
        key = config.security.encryption_key
        if not key:
            raise ConfigurationError(
                "Encryption key not found in secrets",
                details="Please configure security.encryption_key in Streamlit secrets"
            )
        return Fernet(key)
    except Exception as e:
        logger.error(f"Failed to initialize Fernet cipher: {e}")
        raise ConfigurationError(
            "Failed to initialize encryption",
            details=str(e)
        )


def encrypt_token_data(data_dict: Dict[str, Any]) -> Optional[str]:
    """
    Encrypt token data dictionary.
    
    Converts dictionary to JSON string, encrypts it, and returns
    as a base64-encoded string suitable for cookie storage.
    
    Args:
        data_dict: Dictionary containing token data
        
    Returns:
        Optional[str]: Encrypted string or None if encryption fails
    """
    try:
        f = get_fernet()
        
        # 1. Dict -> JSON String
        json_str = json.dumps(data_dict)
        
        # 2. Encrypt (AES via Fernet)
        # Fernet.encrypt requires bytes, returns bytes
        encrypted_bytes = f.encrypt(json_str.encode("utf-8"))
        
        # 3. Bytes -> String (for cookie storage)
        encrypted_str = encrypted_bytes.decode("utf-8")
        
        logger.debug("Successfully encrypted token data")
        return encrypted_str
        
    except ConfigurationError:
        raise
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise EncryptionError(
            "Failed to encrypt token data",
            details=str(e)
        )


def decrypt_token_data(encrypted_str: str) -> Optional[Dict[str, Any]]:
    """
    Decrypt token data string.
    
    Decrypts base64-encoded string and converts back to dictionary.
    
    Args:
        encrypted_str: Encrypted token string
        
    Returns:
        Optional[Dict[str, Any]]: Decrypted dictionary or None if decryption fails
    """
    try:
        f = get_fernet()
        
        # 1. String -> Bytes
        encrypted_bytes = encrypted_str.encode("utf-8")
        
        # 2. Decrypt
        decrypted_bytes = f.decrypt(encrypted_bytes)
        
        # 3. Bytes -> JSON String -> Dict
        json_str = decrypted_bytes.decode("utf-8")
        data_dict = json.loads(json_str)
        
        logger.debug("Successfully decrypted token data")
        return data_dict
        
    except InvalidToken:
        logger.warning("Invalid token - decryption failed (possibly tampered or wrong key)")
        return None
    except ConfigurationError:
        raise
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        return None

