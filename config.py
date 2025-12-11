# ai-sales-assistant/config.py

import os

# --- Application Settings ---
APP_NAME = "AI Sales Assistant"

# --- Google OAuth Configuration ---
# Your Google OAuth Client ID and Secret
# NOTE: It is best practice to store these in environment variables or
# a Streamlit secrets file for security.
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")

# This list specifies the permissions your app needs.
GOOGLE_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly"
]

# --- Google Sheets Configuration ---
SPREADSHEET_ID = os.environ.get("")
SHEET_RANGE = "Sheet1!A:Z"

# --- Firebase Configuration ---
FIREBASE_SERVICE_ACCOUNT_JSON = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")

# --- AI & Automation Configuration ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Mapping for lead statuses
LEAD_STATUS_MAP = {
    "imported": "Imported",
    "sent": "Email Sent",
    "replied": "Replied",
    "interested": "Interested",
    "not_interested": "Not Interested"
}

# Delay for follow-up emails in days
FOLLOW_UP_DELAY_DAYS = [3, 7, 14]

# Placeholder for a Calendly link
CALENDLY_LINK = "https://calendly.com/your-username/30min"
