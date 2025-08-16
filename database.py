# ai-sales-assistant/database.py
import firebase_admin
from firebase_admin import credentials, firestore
import json
import base64
from datetime import datetime
from config import FIREBASE_SERVICE_ACCOUNT_JSON
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, validator
import logging

logging.basicConfig(level=logging.INFO)

# Initialize Firebase Admin SDK
try:
    if not firebase_admin._apps:
        if FIREBASE_SERVICE_ACCOUNT_JSON.startswith("{"):
            service_account_info = json.loads(FIREBASE_SERVICE_ACCOUNT_JSON)
        else:
            service_account_info = json.loads(base64.b64decode(FIREBASE_SERVICE_ACCOUNT_JSON))
        
        cred = credentials.Certificate(service_account_info)
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    logging.info("Firebase Firestore initialized successfully.")
except Exception as e:
    logging.error(f"Failed to initialize Firebase: {e}")
    db = None

# Pydantic data models for validation and type safety
class Lead(BaseModel):
    name: str
    email: str
    company: Optional[str] = None
    title: Optional[str] = None
    industry: Optional[str] = None
    score: str = "Warm"  # Hot, Warm, Cold
    status: str = "imported" # imported, sent, replied, interested, not_interested, ooo, booked
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    campaign_id: Optional[str] = None
    enrichment: Optional[Dict[str, Any]] = {}
    thread_id: Optional[str] = None
    sent_count: int = 0
    replied_to: bool = False
    
    @validator('email')
    def validate_email(cls, v):
        if "@" not in v or "." not in v:
            raise ValueError('Invalid email format')
        return v

class Campaign(BaseModel):
    name: str
    owner_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    prompts: Dict[str, str]
    sequence: List[Dict[str, Any]]
    stats: Dict[str, Any] = {
        "emails_sent": 0,
        "replies_classified": 0,
        "meetings_booked": 0,
    }

class Email(BaseModel):
    subject: str
    body: str
    variant: Optional[str] = "A"
    sent_at: datetime = Field(default_factory=datetime.utcnow)
    delivery_status: str = "pending" # sent, failed
    opens: int = 0
    clicks: int = 0
    reply_status: Optional[str] = None

class Response(BaseModel):
    raw_text: str
    classified_label: str
    sentiment: Optional[str] = None
    handled: bool = False
    received_at: datetime = Field(default_factory=datetime.utcnow)

# Database CRUD helpers
def get_collection_ref(collection_name: str):
    """Returns a Firestore collection reference."""
    if db:
        return db.collection(collection_name)
    else:
        raise ConnectionError("Firestore not initialized.")
    
def get_leads_for_campaign(campaign_id: str) -> List[Dict[str, Any]]:
    """Fetches all leads associated with a specific campaign."""
    try:
        leads = db.collection("leads").where("campaign_id", "==", campaign_id).stream()
        return [lead.to_dict() for lead in leads]
    except Exception as e:
        logging.error(f"Error fetching leads for campaign {campaign_id}: {e}")
        return []

def save_lead(lead_data: Dict[str, Any]) -> str:
    """Saves a single lead to Firestore, using Pydantic for validation."""
    try:
        lead = Lead(**lead_data)
        doc_ref = get_collection_ref("leads").document()
        doc_ref.set(lead.model_dump(by_alias=True))
        return doc_ref.id
    except ConnectionError:
        return ""

def update_lead(lead_id: str, updates: Dict[str, Any]) -> None:
    """Updates a lead's fields in Firestore."""
    try:
        get_collection_ref("leads").document(lead_id).update(updates)
    except ConnectionError:
        pass

def save_campaign(campaign_data: Dict[str, Any]) -> str:
    """Saves a new campaign to Firestore."""
    try:
        campaign = Campaign(**campaign_data)
        doc_ref = get_collection_ref("campaigns").document()
        doc_ref.set(campaign.model_dump(by_alias=True))
        return doc_ref.id
    except ConnectionError:
        return ""

def get_campaigns(owner_id: str) -> List[Dict[str, Any]]:
    """Fetches all campaigns for a given owner."""
    try:
        campaigns_ref = get_collection_ref("campaigns")
        docs = campaigns_ref.where("owner_id", "==", owner_id).stream()
        return [doc.to_dict() for doc in docs]
    except ConnectionError:
        return []

def get_leads_by_status(status: str) -> List[Dict[str, Any]]:
    """Fetches leads with a specific status."""
    try:
        leads_ref = get_collection_ref("leads")
        docs = leads_ref.where("status", "==", status).stream()
        return [doc.to_dict() for doc in docs]
    except ConnectionError:
        return []

def save_email_record(lead_id: str, email_data: Dict[str, Any]) -> None:
    """Saves a sent email record to Firestore as a subcollection under a lead."""
    try:
        email = Email(**email_data)
        get_collection_ref(f"leads/{lead_id}/emails").add(email.model_dump(by_alias=True))
    except ConnectionError:
        pass

def save_response_record(lead_id: str, response_data: Dict[str, Any]) -> None:
    """Saves a received response record to Firestore."""
    try:
        response = Response(**response_data)
        get_collection_ref(f"leads/{lead_id}/responses").add(response.model_dump(by_alias=True))
    except ConnectionError:
        pass

def get_lead_by_thread_id(thread_id: str) -> Optional[Dict[str, Any]]:
    """Finds a lead associated with a Gmail thread ID."""
    try:
        leads_ref = get_collection_ref("leads")
        docs = leads_ref.where("thread_id", "==", thread_id).limit(1).stream()
        for doc in docs:
            return doc.to_dict()
        return None
    except ConnectionError:
        return None