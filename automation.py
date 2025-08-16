# ai-sales-assistant/automation.py

import streamlit as st
import time
import threading
import logging
from datetime import datetime, timedelta

# --- CRITICAL: Import required classes from other modules ---
from integrations import GmailAPI
from database import get_lead_by_thread_id, update_lead
from ai_engine import classify_response, score_lead
from config import FOLLOW_UP_DELAY_DAYS, CALENDLY_LINK, LEAD_STATUS_MAP

# Set up logging for better debugging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SequenceManager:
    """
    Manages the sending of email campaigns and follow-up sequences.
    """
    def __init__(self, credentials):
        self.gmail = GmailAPI(credentials)

    def run_campaign_send(self, campaign, leads):
        """
        Sends the initial email to a list of leads for a given campaign.
        This method is designed to be run in a separate thread.
        """
        logging.info(f"Starting campaign '{campaign['name']}' send process...")
        for i, lead in enumerate(leads):
            try:
                # Placeholder for Gemini API call to generate email
                email_body = f"Hello {lead['name']},\n\nThis is a placeholder for the email content.\n\nBest,\nYour Sales Team"
                subject = f"Your Subject for {lead['company']}"
                
                thread_id = self.gmail.send_email(
                    recipient=lead["email"],
                    subject=subject,
                    body=email_body
                )
                if thread_id:
                    update_lead(
                        lead['id'],
                        {
                            "status": "sent",
                            "thread_id": thread_id,
                            "last_activity": time.time(),
                            "campaign_id": campaign['id'],
                            "sent_count": lead.get("sent_count", 0) + 1
                        }
                    )
                    logging.info(f"Email sent to {lead['email']}. Thread ID: {thread_id}")
            except Exception as e:
                logging.error(f"Failed to send email to {lead['email']}: {e}")
            
            # Simple delay to avoid rate limits
            time.sleep(1)
        logging.info("Campaign send process completed.")

    def send_follow_up(self, lead, step=1):
        """
        Sends a follow-up email based on the sequence step.
        """
        logging.info(f"Sending follow-up email to {lead['email']} (Step {step})...")
        try:
            # Placeholder for Gemini API call to generate follow-up email
            follow_up_body = f"Hi {lead['name']},\n\nJust following up on my previous email.\n\n{CALENDLY_LINK}\n\nBest,\nYour Sales Team"
            subject = f"Re: Your Subject for {lead['company']}"
            
            thread_id = self.gmail.send_email(
                recipient=lead["email"],
                subject=subject,
                body=follow_up_body
            )
            if thread_id:
                update_lead(
                    lead['id'],
                    {
                        "last_activity": time.time(),
                        "sent_count": lead.get("sent_count", 0) + 1
                    }
                )
                logging.info(f"Follow-up sent to {lead['email']}.")
        except Exception as e:
            logging.error(f"Failed to send follow-up to {lead['email']}: {e}")

class ResponseMonitor(threading.Thread):
    """
    A background thread to monitor for new email replies and classify them.
    """
    def __init__(self, credentials, interval=60):
        super().__init__()
        self._stop_event = threading.Event()
        self.interval = interval
        self.gmail = GmailAPI(credentials)

    def run(self):
        """
        The main loop of the thread. Checks for replies and processes them.
        """
        logging.info("ResponseMonitor thread started.")
        while not self._stop_event.is_set():
            self.check_replies()
            time.sleep(self.interval)
        logging.info("ResponseMonitor thread stopped.")

    def check_replies(self):
        """Fetches and processes new replies from Gmail."""
        logging.info("Checking for new replies...")
        try:
            replies = self.gmail.get_replies()
            if not replies:
                logging.info("No new replies found.")
                return

            for reply in replies:
                lead = get_lead_by_thread_id(reply['threadId'])
                if lead:
                    logging.info(f"Reply found for lead {lead['email']}.")
                    
                    # Use AI to classify the response and get a score
                    classification = classify_response(reply['snippet'])
                    score = score_lead(reply['snippet'])
                    
                    # Update lead status and score in Firestore
                    new_status = LEAD_STATUS_MAP.get(classification, "replied")
                    update_lead(
                        lead['id'],
                        {
                            "status": new_status,
                            "last_activity": time.time(),
                            "score": score
                        }
                    )
                    self.gmail.mark_as_read(reply['id'])
                    logging.info(f"Lead {lead['email']} updated to status: {new_status}, score: {score}")

        except Exception as e:
            logging.error(f"Error during reply check: {e}")

    def stop(self):
        """Signals the thread to stop."""
        self._stop_event.set()
