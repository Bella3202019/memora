"""
Call-level memory extraction module.
Analyzes full call transcripts to extract experiences, emotions, and truths.
"""

import os
import json
import logging
from typing import Dict, List, Any
from dotenv import load_dotenv
from openai import AsyncOpenAI

from voice.src.prompts.call_extraction_prompt import CALL_EXTRACTION_PROMPT

load_dotenv()

logger = logging.getLogger(__name__)

openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def format_conversation(messages: List[Dict[str, Any]]) -> str:
    """
    Format messages array into a readable conversation string.
    
    Args:
        messages: List of message dicts with 'role', 'content', 'timestamp'
        
    Returns:
        Formatted conversation string
    """
    conversation_lines = []
    
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        timestamp = msg.get("timestamp", "")
        
        # Format role label
        role_label = "[Agent]" if role == "agent" else "[User]"
        
        # Extract time for readability (HH:MM:SS from ISO timestamp)
        time_str = ""
        if timestamp and len(timestamp) >= 19:
            time_str = f" ({timestamp[11:19]})"
        
        conversation_lines.append(f"{role_label}{time_str}: {content}")
    
    return "\n".join(conversation_lines)


async def extract_from_call(
    call_id: str,
    call_date: str,
    messages: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Extract experiences, emotions, and truths from a full call transcript.
    
    Args:
        call_id: Unique call identifier
        call_date: ISO date string of when the call happened
        messages: List of message dicts from the transcript
        
    Returns:
        Dict containing extracted experiences, emotions, truths, and relationships
    """
    try:
        # Format the conversation
        conversation = format_conversation(messages)
        
        # Extract just the date portion (YYYY-MM-DD) for synthesis dates
        date_only = call_date[:10] if call_date and len(call_date) >= 10 else call_date
        
        # Build the user message with conversation and metadata
        user_content = f"""CALL DATE: {date_only}
CALL ID: {call_id}

CONVERSATION:
{conversation}

---
Extract all experiences, emotions, and truths from this conversation. Use {date_only} as the synthesis_date for any truths."""

        # Call OpenAI
        response = await openai_client.chat.completions.create(
            model="gpt-5.2",
            messages=[
                {
                    "role": "system",
                    "content": CALL_EXTRACTION_PROMPT
                },
                {
                    "role": "user",
                    "content": user_content
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        # Parse the response
        extracted_data = json.loads(response.choices[0].message.content)
        
        # Add call metadata
        extracted_data["call_metadata"] = {
            "call_id": call_id,
            "call_date": call_date,
            "message_count": len(messages)
        }
        
        logger.info(
            f"Extracted from call {call_id}: "
            f"{len(extracted_data.get('experiences', []))} experiences, "
            f"{len(extracted_data.get('emotions', []))} emotions, "
            f"{len(extracted_data.get('truths', []))} truths"
        )
        
        return extracted_data
        
    except Exception as e:
        logger.error(f"Error extracting from call {call_id}: {e}")
        return {
            "experiences": [],
            "emotions": [],
            "truths": [],
            "relationships": {
                "experience_evoked_emotion": [],
                "truth_distilled_from_experience": []
            },
            "call_metadata": {
                "call_id": call_id,
                "call_date": call_date,
                "message_count": len(messages),
                "error": str(e)
            }
        }

