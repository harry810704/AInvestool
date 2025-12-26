"""
Google Drive integration module.

This module handles Google OAuth authentication and Drive API operations
for reading and writing portfolio data.
"""

import streamlit as st
import json
from typing import Optional, List, Dict, Any, Tuple
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build, Resource
from googleapiclient.http import MediaIoBaseUpload
import pandas as pd
import io

from modules.logger import get_logger
from modules.exceptions import AuthenticationError, DriveServiceError
from config import get_config

logger = get_logger(__name__)
logger.info("Initializing drive_manager module (Reloaded)")
config = get_config()


def get_client_config() -> Dict[str, Any]:
    """
    Get Google OAuth client configuration from Streamlit secrets.
    
    Returns:
        Dict[str, Any]: Client configuration dictionary
    """
    return {
        "web": {
            "client_id": st.secrets["google"]["client_id"],
            "client_secret": st.secrets["google"]["client_secret"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [st.secrets["google"]["redirect_uri"]],
        }
    }


def get_auth_flow() -> Flow:
    """
    Create OAuth flow for Google authentication.
    
    Returns:
        Flow: Configured OAuth flow
    """
    return Flow.from_client_config(
        get_client_config(),
        scopes=config.google_drive.scopes,
        redirect_uri=st.secrets["google"]["redirect_uri"],
    )


def get_login_url() -> str:
    """
    Get Google OAuth login URL.
    
    Returns:
        str: Authorization URL for user to visit
    """
    flow = get_auth_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    logger.info("Generated login URL")
    return auth_url


def exchange_code_for_token(code: str) -> Optional[Credentials]:
    """
    Exchange OAuth code for credentials.
    
    Args:
        code: OAuth authorization code
        
    Returns:
        Optional[Credentials]: Google credentials or None if exchange fails
    """
    try:
        flow = get_auth_flow()
        flow.fetch_token(code=code)
        logger.info("Successfully exchanged code for token")
        return flow.credentials
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        st.error(f"認證失敗: {e}")
        return None


# ==========================================
# 🔐 憑證序列化工具 (修改重點)
# ==========================================


def credentials_to_dict(creds: Credentials) -> Dict[str, Any]:
    """
    Convert credentials object to dictionary for serialization.
    
    Args:
        creds: Google credentials object
        
    Returns:
        Dict[str, Any]: Serialized credentials
    """
    return {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }


def credentials_from_dict(creds_dict: Dict[str, Any]) -> Tuple[Optional[Credentials], bool]:
    """
    Restore credentials from dictionary and check/refresh if needed.
    
    Args:
        creds_dict: Serialized credentials dictionary
        
    Returns:
        Tuple[Optional[Credentials], bool]: (credentials, was_refreshed)
            - credentials: Restored credentials or None if invalid
            - was_refreshed: True if token was refreshed
    """
    try:
        # Don't pass scopes to from_authorized_user_info to avoid scope validation issues
        # Google sometimes adds 'openid' automatically, which causes scope mismatch
        creds = Credentials.from_authorized_user_info(creds_dict)

        # Check validity and refresh if needed
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logger.info("Credentials refreshed successfully")
                    return creds, True  # True means refreshed, need to update cookie
                except Exception as e:
                    logger.error(f"Failed to refresh credentials: {e}")
                    return None, False
            else:
                logger.warning("Credentials invalid and cannot be refreshed")
                return None, False

        return creds, False  # False means no refresh needed
    except Exception as e:
        logger.error(f"Failed to restore credentials: {e}")
        return None, False


def get_user_info(creds: Credentials) -> Optional[Dict[str, str]]:
    """
    Get user information from Google OAuth2 API.
    
    Args:
        creds: Google credentials
        
    Returns:
        Optional[Dict[str, str]]: Dictionary with 'email' and 'name' keys, or None if failed
    """
    try:
        # Validate credentials
        if not creds or not creds.valid:
            logger.warning("Invalid credentials provided to get_user_info")
            return None
        
        # Build the OAuth2 service
        service = build('oauth2', 'v2', credentials=creds)
        user_info = service.userinfo().get().execute()
        
        result = {
            'email': user_info.get('email', 'Unknown'),
            'name': user_info.get('name', user_info.get('email', 'User'))
        }
        logger.debug(f"Retrieved user info: {result['email']}")
        return result
    except Exception as e:
        logger.error(f"Failed to get user info: {e}")
        # Return a fallback with minimal info
        return {
            'email': 'user@example.com',
            'name': 'User'
        }


# ==========================================
# Drive API 操作 (維持不變)
# ==========================================
def get_drive_service(creds: Credentials) -> Resource:
    """
    Build Google Drive service from credentials.
    
    Args:
        creds: Google credentials
        
    Returns:
        Resource: Google Drive service instance
    """
    try:
        service = build("drive", "v3", credentials=creds)
        logger.debug("Drive service created successfully")
        return service
    except Exception as e:
        logger.error(f"Failed to create Drive service: {e}")
        raise DriveServiceError("Failed to create Drive service", details=str(e))


def ensure_folder_exists(service: Resource) -> str:
    """
    Ensure application folder exists in Google Drive.
    
    Args:
        service: Google Drive service instance
        
    Returns:
        str: Folder ID
    """
    folder_name = config.google_drive.folder_name
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    
    try:
        results = (
            service.files()
            .list(q=query, spaces="drive", fields="files(id, name)")
            .execute()
        )
        files = results.get("files", [])
        
        if not files:
            # Create folder
            file_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
            }
            folder = service.files().create(body=file_metadata, fields="id").execute()
            folder_id = folder.get("id")
            logger.info(f"Created folder '{folder_name}' with ID: {folder_id}")
            return folder_id
        else:
            folder_id = files[0].get("id")
            logger.debug(f"Found existing folder '{folder_name}' with ID: {folder_id}")
            return folder_id
    except Exception as e:
        logger.error(f"Failed to ensure folder exists: {e}")
        raise DriveServiceError("Failed to access Drive folder", details=str(e))


def get_file_id(service: Resource, folder_id: str, filename: str) -> Optional[str]:
    """
    Get file ID by name within a folder.
    
    Args:
        service: Google Drive service instance
        folder_id: Parent folder ID
        filename: Name of file to find
        
    Returns:
        Optional[str]: File ID or None if not found
    """
    query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
    try:
        results = (
            service.files()
            .list(q=query, spaces="drive", fields="files(id, name)")
            .execute()
        )
        files = results.get("files", [])
        file_id = files[0].get("id") if files else None
        
        if file_id:
            logger.debug(f"Found file '{filename}' with ID: {file_id}")
        else:
            logger.debug(f"File '{filename}' not found")
        
        return file_id
    except Exception as e:
        logger.error(f"Failed to get file ID for '{filename}': {e}")
        return None


def read_csv_from_drive(service: Resource, filename: str) -> List[dict]:
    """
    Read CSV file from Google Drive.
    
    Args:
        service: Google Drive service instance
        filename: Name of CSV file to read
        
    Returns:
        List[dict]: List of records from CSV
    """
    try:
        folder_id = ensure_folder_exists(service)
        file_id = get_file_id(service, folder_id, filename)
        if not file_id:
            logger.info(f"File '{filename}' not found, returning empty list")
            return []
        
        request = service.files().get_media(fileId=file_id)
        file_content = request.execute()
        df = pd.read_csv(io.BytesIO(file_content))
        
        logger.info(f"Read {len(df)} records from '{filename}'")
        return df.to_dict("records")
    except Exception as e:
        logger.error(f"Failed to read CSV '{filename}': {e}")
        st.error(f"讀取雲端檔案失敗: {e}")
        return []


def save_csv_to_drive(service: Resource, filename: str, data: List[dict]) -> None:
    """
    Save CSV file to Google Drive.
    
    Args:
        service: Google Drive service instance
        filename: Name of CSV file to save
        data: List of records to save
    """
    try:
        folder_id = ensure_folder_exists(service)
        file_id = get_file_id(service, folder_id, filename)
        df = pd.DataFrame(data)
        csv_buffer = io.BytesIO()
        df.to_csv(csv_buffer, index=False)
        media = MediaIoBaseUpload(csv_buffer, mimetype="text/csv", resumable=True)
        
        if file_id:
            service.files().update(fileId=file_id, media_body=media).execute()
            logger.info(f"Updated CSV '{filename}' with {len(data)} records")
        else:
            file_metadata = {"name": filename, "parents": [folder_id]}
            service.files().create(
                body=file_metadata, media_body=media, fields="id"
            ).execute()
            logger.info(f"Created CSV '{filename}' with {len(data)} records")
    except Exception as e:
        logger.error(f"Failed to save CSV '{filename}': {e}")
        st.error(f"存檔至雲端失敗: {e}")


def read_json_from_drive(service: Resource, filename: str) -> Optional[dict]:
    """
    Read JSON file from Google Drive.
    
    Args:
        service: Google Drive service instance
        filename: Name of JSON file to read
        
    Returns:
        Optional[dict]: Parsed JSON data or None if not found/error
    """
    try:
        folder_id = ensure_folder_exists(service)
        file_id = get_file_id(service, folder_id, filename)
        if not file_id:
            logger.info(f"JSON file '{filename}' not found")
            return None
        
        content = service.files().get_media(fileId=file_id).execute()
        data = json.loads(content.decode("utf-8"))
        logger.info(f"Read JSON from '{filename}'")
        return data
    except Exception as e:
        logger.error(f"Failed to read JSON '{filename}': {e}")
        st.error(f"讀取 JSON 失敗: {e}")
        return None


def save_json_to_drive(service: Resource, filename: str, data: dict) -> None:
    """
    Save JSON file to Google Drive.
    
    Args:
        service: Google Drive service instance
        filename: Name of JSON file to save
        data: Dictionary to save as JSON
    """
    try:
        folder_id = ensure_folder_exists(service)
        file_id = get_file_id(service, folder_id, filename)
        json_str = json.dumps(data, ensure_ascii=False, indent=4)
        media = MediaIoBaseUpload(
            io.BytesIO(json_str.encode("utf-8")),
            mimetype="application/json",
            resumable=True,
        )
        
        if file_id:
            service.files().update(fileId=file_id, media_body=media).execute()
            logger.info(f"Updated JSON '{filename}'")
        else:
            file_metadata = {"name": filename, "parents": [folder_id]}
            service.files().create(
                body=file_metadata, media_body=media, fields="id"
            ).execute()
            logger.info(f"Created JSON '{filename}'")
    except Exception as e:
        logger.error(f"Failed to save JSON '{filename}': {e}")
        st.error(f"JSON 存檔失敗: {e}")


def read_excel_from_drive(service: Resource, filename: str) -> List[dict]:
    """
    Read Excel file from Google Drive.

    Args:
        service: Google Drive service instance
        filename: Name of Excel file to read

    Returns:
        List[dict]: List of records from Excel
    """
    try:
        folder_id = ensure_folder_exists(service)
        file_id = get_file_id(service, folder_id, filename)
        if not file_id:
            logger.info(f"Excel file '{filename}' not found, returning empty list")
            return []

        request = service.files().get_media(fileId=file_id)
        file_content = request.execute()

        # Read Excel using pandas
        # Note: openpyxl must be installed
        df = pd.read_excel(io.BytesIO(file_content))

        logger.info(f"Read {len(df)} records from '{filename}'")
        return df.to_dict("records")
    except Exception as e:
        logger.error(f"Failed to read Excel '{filename}': {e}")
        st.error(f"讀取 Excel 失敗: {e}")
        return []


def save_excel_to_drive(service: Resource, filename: str, data: Any) -> None:
    """
    Save data to Excel file in Google Drive.

    Args:
        service: Google Drive service instance
        filename: Name of Excel file to save
        data: Data to save (List of dicts or DataFrame)
    """
    try:
        folder_id = ensure_folder_exists(service)
        file_id = get_file_id(service, folder_id, filename)

        # Convert to DataFrame if list of dicts
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, pd.DataFrame):
            df = data
        else:
            logger.error("Invalid data type for Excel save")
            return

        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False, engine='openpyxl')

        # Reset buffer position
        excel_buffer.seek(0)

        # Use appropriate MIME type for XLSX
        media = MediaIoBaseUpload(
            excel_buffer,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            resumable=True
        )

        if file_id:
            service.files().update(fileId=file_id, media_body=media).execute()
            logger.info(f"Updated Excel '{filename}' with {len(df)} records")
        else:
            file_metadata = {"name": filename, "parents": [folder_id]}
            service.files().create(
                body=file_metadata, media_body=media, fields="id"
            ).execute()
            logger.info(f"Created Excel '{filename}' with {len(df)} records")
    except Exception as e:
        logger.error(f"Failed to save Excel '{filename}': {e}")
        st.error(f"Excel 存檔失敗: {e}")


def upload_file_stream(
    service: Resource, 
    file_obj: io.BytesIO, 
    filename: str, 
    folder_name: str, 
    mime_type: str = "application/octet-stream"
) -> None:
    """
    Upload a file stream to Google Drive.
    
    Args:
        service: Google Drive service instance
        file_obj: File object to upload
        filename: Name of file
        folder_name: Name of parent folder (used for logging/verification)
        mime_type: MIME type of file
    """
    try:
        # Note: ensure_folder_exists currently uses config.google_drive.folder_name
        # We assume folder_name passed here matches or we default to config
        folder_id = ensure_folder_exists(service)
        
        file_id = get_file_id(service, folder_id, filename)
        
        media = MediaIoBaseUpload(file_obj, mimetype=mime_type, resumable=True)
        
        if file_id:
            service.files().update(fileId=file_id, media_body=media).execute()
            logger.info(f"Updated '{filename}' via stream")
        else:
            file_metadata = {"name": filename, "parents": [folder_id]}
            service.files().create(
                body=file_metadata, media_body=media, fields="id"
            ).execute()
            logger.info(f"Created '{filename}' via stream")
            
    except Exception as e:
        logger.error(f"Failed to upload stream '{filename}': {e}")
        st.error(f"上傳失敗: {e}")
