# ai-sales-assistant/app.py

import streamlit as st
import pandas as pd
import json
import firebase_admin
from firebase_admin import credentials, firestore
import logging
import os
import threading
import time

# --- ALL IMPORTS ARE AT THE TOP OF THE FILE ---
from auth import is_authenticated, login_button, get_credentials, get_user_info
from database import (
    get_leads_for_campaign, save_lead, save_campaign, get_campaigns,
    update_lead, get_leads_by_status, get_lead_by_thread_id
)
from integrations import GoogleSheetsAPI, GmailAPI, GeminiAPI
from ai_engine import generate_cold_email, classify_response, score_lead
from automation import SequenceManager, ResponseMonitor
from config import APP_NAME, LEAD_STATUS_MAP, CALENDLY_LINK, FOLLOW_UP_DELAY_DAYS, FIREBASE_SERVICE_ACCOUNT_JSON, SPREADSHEET_ID, SHEET_RANGE

# Set up logging for better debugging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- App Initialization & Firebase Setup ---
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(f"🚀 {APP_NAME}")

try:
    if not firebase_admin._apps:
        # Load the service account key from the environment variable
        creds_dict = json.loads(FIREBASE_SERVICE_ACCOUNT_JSON)
        creds = credentials.Certificate(creds_dict)
        firebase_admin.initialize_app(creds)
    db = firestore.client()
except Exception as e:
    st.error(f"Failed to initialize Firebase: {e}")
    # Stop the app if Firebase fails to connect, as it's a critical dependency
    st.stop()

# --- Streamlit Session State & Helper Functions ---
def get_session_manager():
    """Returns a singleton instance of the SequenceManager."""
    if "seq_manager" not in st.session_state:
        creds = get_credentials()
        if creds:
            st.session_state["seq_manager"] = SequenceManager(creds)
    return st.session_state.get("seq_manager")

def get_session_monitor():
    """Returns a singleton instance of the ResponseMonitor thread."""
    if "resp_monitor" not in st.session_state:
        creds = get_credentials()
        if creds:
            st.session_state["resp_monitor"] = ResponseMonitor(creds)
    return st.session_state.get("resp_monitor")

def start_monitor():
    """Starts the background response monitor thread."""
    monitor = get_session_monitor()
    if monitor and not monitor.is_alive():
        monitor.start()
        st.success("Response monitoring started in the background.")

def stop_monitor():
    """Stops the background response monitor thread."""
    monitor = get_session_monitor()
    if monitor and monitor.is_alive():
        monitor.stop()
        monitor.join()
        st.warning("Response monitoring stopped.")

# --- UI Navigation & Authentication Flow ---
if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

if not is_authenticated():
    st.header("Connect your Google Account")
    st.info("This application requires access to your Google account to manage emails and campaigns.")
    login_button()
    st.stop()

page = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard", "Lead Management", "AI Email Studio", "Campaign Builder",
        "Response Monitor", "Analytics", "Settings"
    ]
)
st.sidebar.markdown(f"**Logged in as:** {get_user_info()['email']}")

# --- Main Page Logic ---
if page == "Dashboard":
    st.header("📊 AI Sales Dashboard")
    st.info("Your command center for all campaign activities. "
            "See lead health, performance metrics, and a quick summary of your pipeline.")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Lead Health")
        leads_by_status = {
            "interested": get_leads_by_status("interested"),
            "sent": get_leads_by_status("sent"),
            "imported": get_leads_by_status("imported"),
            "not_interested": get_leads_by_status("not_interested")
        }

        hot_count = len(leads_by_status["interested"])
        warm_count = len(leads_by_status["sent"])
        imported_count = len(leads_by_status["imported"])
        closed_count = len(leads_by_status["not_interested"])
        total_count = hot_count + warm_count + imported_count + closed_count

        st.metric("🔥 Hot Leads", hot_count)
        st.metric("📧 Sent Leads", warm_count)
        st.metric("🔵 Imported Leads", imported_count)
        st.metric("🚫 Closed Leads", closed_count)
        st.metric("Total Leads", total_count)

    with col2:
        st.subheader("Campaign Stats")
        st.metric("Emails Sent", "N/A")
        st.metric("Meetings Booked", "N/A")
        st.metric("Response Rate", "N/A")

    with col3:
        st.subheader("Lead Pipeline")
        st.warning("Pipeline visualization coming soon.")

elif page == "Lead Management":
    st.header("📋 Lead Management")
    tab1, tab2 = st.tabs(["Import from Google Sheets", "View Leads"])

    with tab1:
        st.subheader("Import Leads")
        st.info("Select a Google Sheet and map the columns to import your leads.")
        try:
            sheets_api = GoogleSheetsAPI(get_credentials())
            sheets_list = sheets_api.list_sheets()
            if not sheets_list:
                st.warning("No Google Sheets found. Make sure the sheets are public "
                           "or you have the correct permissions.")
                st.stop()

            sheet_names = [s['name'] for s in sheets_list]
            selected_sheet_name = st.selectbox("Select a Google Sheet", sheet_names)
            selected_sheet_id = [s['id'] for s in sheets_list if s['name'] == selected_sheet_name][0]
            
            try:
                values = sheets_api.read_sheet_data(spreadsheet_id=SPREADSHEET_ID, range_name=SHEET_RANGE)
                if values:
                    df = pd.DataFrame(values[1:], columns=values[0])
                else:
                    st.warning("The selected sheet is empty or has no data.")
                    st.stop()
            except Exception as e:
                logging.warning(f"Failed to read real sheet data: {e}. Using mock data.")
                mock_data = [
                    ["name", "email", "company", "title", "industry"],
                    ["John Doe", "john.doe@example.com", "Acme Inc.", "Head of Sales", "Software"],
                    ["Jane Smith", "jane.smith@example.net", "Globex Corp.", "Marketing Manager", "Technology"]
                ]
                df = pd.DataFrame(mock_data[1:], columns=mock_data[0])

            st.write("First 5 rows of your sheet:")
            st.dataframe(df.head())
            col_mappings = {}
            st.markdown("### Map Columns")
            cols = st.columns(4)

            with cols[0]:
                col_mappings['name'] = st.selectbox("Name Column", df.columns, index=df.columns.get_loc('name') if 'name' in df.columns else 0)
            with cols[1]:
                col_mappings['email'] = st.selectbox("Email Column", df.columns, index=df.columns.get_loc('email') if 'email' in df.columns else 1)
            with cols[2]:
                col_mappings['company'] = st.selectbox("Company Column", df.columns, index=df.columns.get_loc('company') if 'company' in df.columns else 2)
            with cols[3]:
                col_mappings['title'] = st.selectbox("Title Column", df.columns, index=df.columns.get_loc('title') if 'title' in df.columns else 3)
            
            if st.button("Import Leads", use_container_width=True):
                if not df.empty:
                    imported_count = 0
                    for _, row in df.iterrows():
                        try:
                            lead_data = {
                                "name": row[col_mappings['name']],
                                "email": row[col_mappings['email']],
                                "company": row[col_mappings['company']],
                                "title": row[col_mappings['title']],
                                "status": "imported",
                                "campaign_id": "temp_campaign_123",
                                "created_at": time.time(),
                                "last_activity": time.time()
                            }
                            if "@" in lead_data["email"] and lead_data["name"]:
                                save_lead(lead_data)
                                imported_count += 1
                        except KeyError as ke:
                            st.warning(f"Skipping row due to missing column mapping for {ke}.")
                        except Exception as import_e:
                            st.error(f"Error saving lead: {import_e}")
                    st.success(f"Successfully imported {imported_count} leads!")
                else:
                    st.error("No data found in the selected sheet.")
        except Exception as e:
            st.error(f"An error occurred: {e}. Please ensure your credentials and permissions are correct.")

    with tab2:
        st.subheader("View All Leads")
        st.info("Browse your imported leads and their current status.")
        leads = (
            get_leads_by_status("imported")
            + get_leads_by_status("sent")
            + get_leads_by_status("replied")
        )
        if leads:
            leads_df = pd.DataFrame(leads)
            leads_df = leads_df[['name', 'email', 'company', 'title', 'status', 'score', 'last_activity']]
            leads_df['last_activity'] = pd.to_datetime(leads_df['last_activity'], unit='s')
            st.dataframe(leads_df, use_container_width=True)
        else:
            st.info("No leads found. Go to the 'Import' tab to add some.")

elif page == "AI Email Studio":
    st.header("✍️ AI Email Studio")
    st.info("Generate personalized emails, preview them, and send them to your leads.")

    campaigns = get_campaigns(get_user_info()["id"])
    if not campaigns:
        st.warning("No campaigns found. Go to 'Campaign Builder' to create one.")
        st.stop()

    selected_campaign = st.selectbox("Select a Campaign", [c['name'] for c in campaigns])
    campaign_id = [c['id'] for c in campaigns if c['name'] == selected_campaign][0]

    leads_to_send = get_leads_by_status("imported")
    if not leads_to_send:
        st.info("No leads available to send to. Please import some leads first.")
        st.stop()

    st.markdown("### Preview & Send Emails")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Lead Selection")
        selected_lead_name = st.selectbox("Select a Lead to Preview", [l['name'] for l in leads_to_send])
        selected_lead = [l for l in leads_to_send if l['name'] == selected_lead_name][0]
        
        st.write(f"**Company:** {selected_lead.get('company', 'N/A')}")
        st.write(f"**Title:** {selected_lead.get('title', 'N/A')}")
        st.write(f"**Status:** {LEAD_STATUS_MAP.get(selected_lead.get('status', 'imported'), 'Unknown')}")

        if st.button("Generate Email Preview", use_container_width=True):
            with st.spinner("Generating email with Gemini..."):
                email_content = generate_cold_email(selected_lead, campaign_id)
                st.session_state["preview_email"] = email_content
                st.session_state["preview_lead_id"] = selected_lead['id']
                st.success("Preview generated!")

    with col2:
        st.subheader("Email Preview")
        if "preview_email" in st.session_state:
            email = st.session_state["preview_email"]
            st.text_input("Subject", value=email["subject"], key="edited_subject")
            st.text_area("Body", value=email["body"], height=300, key="edited_body")

            if st.button("Send This Email", use_container_width=True):
                creds = get_credentials()
                if creds:
                    seq_manager = get_session_manager()
                    try:
                        thread_id = seq_manager.gmail.send_email(
                            recipient=selected_lead["email"],
                            subject=st.session_state.edited_subject,
                            body=st.session_state.edited_body
                        )
                        update_lead(
                            st.session_state["preview_lead_id"],
                            {
                                "status": "sent",
                                "thread_id": thread_id,
                                "last_activity": time.time(),
                                "campaign_id": campaign_id,
                                "sent_count": selected_lead.get("sent_count", 0) + 1
                            }
                        )
                        st.success(f"Email sent to {selected_lead['name']}!")
                        del st.session_state["preview_email"]
                        del st.session_state["preview_lead_id"]
                        st.experimental_rerun()
                    except Exception as e:
                        st.error(f"Failed to send email: {e}")
        else:
            st.info("Generate an email preview on the left to see it here.")

elif page == "Campaign Builder":
    st.header("🏗️ Campaign Builder")
    st.info("Create and customize your multi-step email campaigns.")

    with st.form("new_campaign_form"):
        campaign_name = st.text_input("Campaign Name", "My First Campaign")
        st.markdown("### AI Prompts")
        prompt1 = st.text_area(
            "Initial Email Prompt",
            "Generate a highly personalized cold email from scratch for a B2B sales outreach. "
            "Focus on a pain point relevant to the lead's job title and company. "
            "End with a call to action for a meeting.",
            height=150
        )
        submitted = st.form_submit_button("Create Campaign", use_container_width=True)
        if submitted:
            if campaign_name and prompt1:
                campaign_data = {
                    "name": campaign_name,
                    "owner_id": get_user_info()["id"],
                    "prompts": {"initial_email": prompt1},
                    "sequence": [{"step": 1, "delay_days": FOLLOW_UP_DELAY_DAYS[0]}]
                }
                save_campaign(campaign_data)
                st.success(f"Campaign '{campaign_name}' created!")
                st.experimental_rerun()
            else:
                st.warning("Please provide a campaign name and an initial email prompt.")

    st.markdown("---")
    st.markdown("### Existing Campaigns")
    user_campaigns = get_campaigns(get_user_info()["id"])
    if user_campaigns:
        for campaign in user_campaigns:
            with st.expander(campaign['name']):
                st.write(f"**Prompts:** {campaign['prompts']}")
                st.write(f"**Sequence:** {campaign['sequence']}")
                if st.button(f"Run Campaign '{campaign['name']}'", key=f"run_{campaign['id']}"):
                    with st.spinner("Running campaign..."):
                        leads = get_leads_for_campaign(campaign['id'])
                        if leads:
                            seq_manager = get_session_manager()
                            threading.Thread(target=seq_manager.run_campaign_send, args=(campaign, leads)).start()
                            st.success(f"Campaign '{campaign['name']}' started for {len(leads)} leads.")
                        else:
                            st.warning("No leads found for this campaign.")
    else:
        st.info("You have no campaigns yet. Create one above!")

elif page == "Response Monitor":
    st.header("👀 Response Monitor")
    st.info("Manually poll for new replies and classify them with AI.")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Manual Control")
        if st.button("Run Response Monitor Once", use_container_width=True):
            creds = get_credentials()
            if creds:
                with st.spinner("Checking for new replies..."):
                    monitor = ResponseMonitor(creds)
                    monitor.run()
                    st.success("Check complete. Lead statuses have been updated.")

    with col2:
        st.markdown("### Background Polling (Local Only)")
        st.warning("Note: Background polling will not work on Streamlit Cloud. It is for local development only.")
        if st.button("Start Background Monitor", use_container_width=True):
            start_monitor()
        if st.button("Stop Background Monitor", use_container_width=True):
            stop_monitor()

    st.markdown("---")
    st.markdown("### Recently Classified Replies")
    replied_leads = get_leads_by_status("replied")
    if replied_leads:
        leads_df = pd.DataFrame(replied_leads)
        st.dataframe(leads_df[['name', 'email', 'status', 'score']], use_container_width=True)
    else:
        st.info("No new replies to display yet.")

elif page == "Analytics":
    st.header("📈 Analytics")
    st.info("Performance metrics for your campaigns. This is a placeholder for future charts.")
    st.markdown("### Placeholder Analytics")
    st.write("Emails Sent: N/A")
    st.write("Response Rate: N/A")
    st.write("Meetings Booked: N/A")

elif page == "Settings":
    st.header("⚙️ Settings")
    st.info("Manage your integrations and preferences.")
    st.markdown("### Integrations")
    st.write(f"**Google Account:** {get_user_info()['email']}")
    st.markdown("### Calendly Link")
    st.markdown(f"**Current Link:** `{CALENDLY_LINK}`")
    st.info("To change this, update the `CALENDLY_LINK` variable in your `.streamlit/secrets.toml` or `.env` file.")
    st.markdown("---")
    st.markdown("### Development Settings")
    if st.checkbox("Enable Mock Mode (Skip API Calls)"):
        st.info("Mock mode is enabled. No real API calls will be made.")
        st.session_state["mock_mode"] = True
    else:
        st.session_state["mock_mode"] = False
