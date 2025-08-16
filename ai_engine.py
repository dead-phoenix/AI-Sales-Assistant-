# ai-sales-assistant/ai_engine.py
from typing import Dict, Any, Optional
from integrations import GeminiAPI
from config import CALENDLY_LINK
import logging
import json

logging.basicConfig(level=logging.INFO)

gemini = GeminiAPI()

def generate_cold_email(lead: Dict[str, Any], prompt: str) -> Dict[str, str]:
    """
    Generates a personalized cold email (subject and body) for a lead.
    
    Args:
        lead (Dict[str, Any]): A dictionary containing lead information (name, company, title, industry).
        prompt (str): The base prompt to guide the AI.
        
    Returns:
        Dict[str, str]: A dictionary with 'subject' and 'body' of the generated email.
    """
    try:
        # Pre-process prompt to be more conversational and dynamic
        enriched_prompt = f"""
        You are an expert sales representative. Your goal is to write a highly personalized, value-forward cold email to a specific person without using any templates. The tone should be concise and professional.
        
        The person you're emailing is {lead.get('name', 'there')}, a {lead.get('title', 'manager')} at {lead.get('company', 'their company')}. Their industry is {lead.get('industry', 'unknown')}.
        
        Based on this information, identify a potential pain point they might have and offer a brief, relevant solution.
        
        The email must include a call-to-action asking them to book a brief meeting using this Calendly link: {CALENDLY_LINK}. Do not mention Calendly by name, just embed the link naturally.
        
        Write both a subject line and the email body. Format your response as a JSON object with 'subject' and 'body' keys.
        
        Example JSON:
        {{
          "subject": "Quick question about pain_point",
          "body": "Hi {lead.get('name', 'there')}, ... your email content ... {CALENDLY_LINK}."
        }}
        """
        
        ai_response_text = gemini.generate_content(enriched_prompt)
        # Attempt to parse JSON response
        try:
            email_parts = json.loads(ai_response_text)
            subject = email_parts.get('subject', 'Default Subject')
            body = email_parts.get('body', 'Default Body')
        except json.JSONDecodeError:
            # Fallback for when the AI doesn't return a perfect JSON
            logging.warning("AI response was not valid JSON. Attempting to parse manually.")
            subject = ai_response_text.split('"subject": "')[1].split('"')[0]
            body = ai_response_text.split('"body": "')[1].split('"')[0].replace('\\n', '\n')

        # Insert Calendly link smartly. The prompt asks AI to embed it, but we can double-check.
        if CALENDLY_LINK not in body:
            body += f"\n\nWould you be open to a quick 15-minute chat next week? Here's my booking link: {CALENDLY_LINK}"
            
        return {"subject": subject, "body": body}

    except Exception as e:
        logging.error(f"Error generating cold email: {e}")
        return {
            "subject": f"Quick question for {lead.get('name', 'you')}",
            "body": f"Hi {lead.get('name', 'there')},\n\nI was reaching out about {lead.get('company', 'your company')}. Would you have 15 minutes to chat? Here's a link to my calendar: {CALENDLY_LINK}\n\nBest,\nYour AI Assistant"
        }

def classify_response(email_body: str) -> str:
    """
    Classifies an email reply into 'Interested', 'Not Interested', 'Neutral', or 'OOO'.
    
    Args:
        email_body (str): The text content of the email reply.
        
    Returns:
        str: The classified label.
    """
    try:
        prompt = f"""
        Classify the following email reply into one of these exact categories: 'interested', 'not_interested', 'neutral', or 'ooo' (out of office).
        
        Email body:
        "{email_body}"
        
        Only respond with the single category name, nothing else.
        """
        classification = gemini.generate_content(prompt).strip().lower().replace(" ", "_")
        
        if classification in ['interested', 'not_interested', 'neutral', 'ooo']:
            return classification
        
        return 'neutral' # Default fallback
    except Exception as e:
        logging.error(f"Error classifying response: {e}")
        return 'neutral' # Graceful fallback

def score_lead(current_status: str) -> str:
    """
    Updates a lead's score based on their current status.
    
    Args:
        current_status (str): The current status of the lead.
        
    Returns:
        str: The new lead score ('Hot', 'Warm', 'Cold').
    """
    status_to_score = {
        "interested": "Hot",
        "replied": "Warm",
        "neutral": "Warm",
        "imported": "Warm",
        "sent": "Warm",
        "ooo": "Warm",
        "not_interested": "Cold",
        "booked": "Hot",
    }
    return status_to_score.get(current_status, "Warm")

# Minimal unit tests
# def test_classify_response_interested():
#     assert classify_response("I'm interested, can we talk more?") == "interested"
# def test_classify_response_ooo():
#     assert classify_response("I'll be out of the office until next week.") == "ooo"