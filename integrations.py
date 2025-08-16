# ai-sales-assistant/integrations.py

import os
import streamlit as st
import google.auth
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import base64
from email.mime.text import MIMEText
import logging
from config import GEMINI_API_KEY, SPREADSHEET_ID, SHEET_RANGE

# Set up logging for better debugging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class GoogleSheetsAPI:
    def __init__(self, credentials):
        self.creds = credentials
        self.service = self.get_service()

    def get_service(self):
        """Builds and returns the Google Sheets service."""
        try:
            return build('sheets', 'v4', credentials=self.creds)
        except Exception as e:
            logging.error(f"Failed to build Google Sheets service: {e}")
            return None

    def list_sheets(self):
        """Lists all sheets the authenticated user has access to."""
        try:
            drive_service = build('drive', 'v3', credentials=self.creds)
            results = drive_service.files().list(
                q="mimeType='application/vnd.google-apps.spreadsheet'",
                spaces='drive',
                fields='nextPageToken, files(id, name)').execute()
            items = results.get('files', [])
            return items
        except Exception as e:
            logging.error(f"Failed to list Google Sheets: {e}")
            return []

    def read_sheet_data(self, spreadsheet_id=SPREADSHEET_ID, range_name=SHEET_RANGE):
        """Reads and returns data from a specified Google Sheet range."""
        if not self.service:
            logging.error("Google Sheets service is not available.")
            return []
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            values = result.get('values', [])
            return values
        except Exception as e:
            logging.error(f"Failed to read sheet data: {e}")
            return []

class GmailAPI:
    def __init__(self, credentials):
        self.creds = credentials
        self.service = self.get_service()

    def get_service(self):
        """Builds and returns the Gmail service."""
        try:
            return build('gmail', 'v1', credentials=self.creds)
        except Exception as e:
            logging.error(f"Failed to build Gmail service: {e}")
            return None

    def send_email(self, recipient, subject, body):
        """Sends an email and returns the thread ID."""
        if not self.service:
            logging.error("Gmail service is not available.")
            return None
        try:
            message = MIMEText(body)
            message['to'] = recipient
            message['subject'] = subject
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            
            message_body = {'raw': raw_message}
            send_message = self.service.users().messages().send(
                userId="me",
                body=message_body
            ).execute()
            logging.info(f"Email sent successfully. Message ID: {send_message['id']}")
            return send_message['threadId']
        except Exception as e:
            logging.error(f"Failed to send email: {e}")
            raise

    def get_replies(self):
        """Fetches new replies from the user's inbox."""
        if not self.service:
            logging.error("Gmail service is not available.")
            return []
        try:
            # We are looking for unread replies that are not from us
            query = "is:unread from:(*-no-reply*|*@*)"
            results = self.service.users().messages().list(userId="me", q=query).execute()
            messages = results.get("messages", [])
            
            replies = []
            for msg in messages:
                message_details = self.service.users().messages().get(userId="me", id=msg['id'], format='full').execute()
                
                # Check if this is a reply (e.g., has a 'References' header) and not a new email
                headers = message_details['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                
                # Simple heuristic: if the subject starts with "Re:", it's likely a reply
                if subject.lower().startswith("re:"):
                    replies.append({
                        "id": message_details['id'],
                        "threadId": message_details['threadId'],
                        "snippet": message_details['snippet'],
                        "subject": subject,
                        "payload": message_details['payload']
                    })
            return replies
        except Exception as e:
            logging.error(f"Failed to get replies: {e}")
            return []

    def mark_as_read(self, message_id):
        """Marks a message as read."""
        if not self.service:
            logging.error("Gmail service is not available.")
            return
        try:
            self.service.users().messages().modify(
                userId="me",
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            logging.info(f"Message {message_id} marked as read.")
        except Exception as e:
            logging.error(f"Failed to mark message {message_id} as read: {e}")

class GeminiAPI:
    def __init__(self):
        self.api_key = GEMINI_API_KEY
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
        
    def generate_text(self, prompt, model="gemini-pro"):
        """Generates text using the Gemini API."""
        if not self.api_key:
            logging.error("Gemini API key is missing.")
            return None

        # Placeholder for API call
        # In a real-world scenario, you would use a library like `google-generativeai`
        # or `requests` to make a POST request to the API with the prompt.
        logging.info(f"Generating content with prompt: {prompt}")

        # Mocking a response for now to prevent app crash
        mock_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "Subject: A Subject Line\n\nBody of the email. This is a placeholder for the generated content."
                            }
                        ]
                    }
                }
            ]
        }
        
        try:
            # This is a placeholder for the actual API call logic
            # response = requests.post(
            #     self.base_url,
            #     headers={"Content-Type": "application/json"},
            #     json={"contents": [{"parts": [{"text": prompt}]}]},
            #     params={"key": self.api_key}
            # ).json()
            
            response = mock_response
            text_content = response['candidates'][0]['content']['parts'][0]['text']
            return text_content
        except Exception as e:
            logging.error(f"Gemini API call failed: {e}")
            return None
