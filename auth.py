# ai-sales-assistant/auth.py

import streamlit as st
import streamlit_pydantic as spd
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import os
import time
import logging

# --- CRITICAL: Import required variables from config.py ---
# This line has been corrected to use GOOGLE_OAUTH_SCOPES
from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_OAUTH_SCOPES

# Set up logging for better debugging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Helper Functions for Google Authentication ---

def get_flow():
    """Initializes and returns the Google OAuth flow."""
    return Flow.from_client_config(
        client_config={
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost:8501"]
            }
        },
        scopes=GOOGLE_OAUTH_SCOPES
    )

def is_authenticated():
    """Checks if the user has valid credentials in the session state."""
    if "credentials" in st.session_state and st.session_state.credentials.valid:
        if st.session_state.credentials.expired and st.session_state.credentials.refresh_token:
            # Refresh the token if it's expired
            st.session_state.credentials.refresh(st.auth_request)
            logging.info("Google credentials refreshed.")
        return True
    return False

def get_credentials():
    """Returns the Google credentials from the session state."""
    return st.session_state.get("credentials", None)

def get_user_info():
    """
    Fetches and returns the user's profile information (name, email).
    This function caches the result in the session state to avoid repeated API calls.
    """
    if "user_info" not in st.session_state or time.time() - st.session_state.get("user_info_timestamp", 0) > 3600:
        creds = get_credentials()
        if creds:
            try:
                service = build('oauth2', 'v2', credentials=creds)
                user_info = service.userinfo().get().execute()
                st.session_state["user_info"] = user_info
                st.session_state["user_info_timestamp"] = time.time()
                logging.info(f"User info fetched: {user_info['email']}")
            except Exception as e:
                logging.error(f"Error fetching user info: {e}")
                st.session_state["user_info"] = {"email": "unknown", "id": "unknown"}
    return st.session_state["user_info"]


# --- Streamlit UI Components ---

def login_button():
    """
    Displays a login button and handles the authentication process.
    """
    flow = get_flow()
    if "credentials" not in st.session_state:
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        st.session_state['flow_state'] = state
        st.markdown(f"""
        <a href="{authorization_url}" target="_self">
            <button style="
                background-color: #4285F4;
                color: white;
                border: none;
                padding: 10px 24px;
                text-align: center;
                text-decoration: none;
                display: inline-block;
                font-size: 16px;
                border-radius: 5px;
                cursor: pointer;
            ">
                Sign in with Google
            </button>
        </a>
        """, unsafe_allow_html=True)
        auth_code = st.query_params.get("code")
        if auth_code:
            try:
                flow.fetch_token(code=auth_code[0])
                st.session_state['credentials'] = flow.credentials
                st.success("Authentication successful! You can now use the app.")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Authentication failed: {e}")
                st.warning("Please try again.")
    else:
        if st.button("Logout"):
            if "credentials" in st.session_state:
                del st.session_state["credentials"]
            if "user_info" in st.session_state:
                del st.session_state["user_info"]
            st.success("You have been logged out.")
            st.experimental_rerun()
