"""
Diary extractor module for extracting memories from diary entries.
Processes markdown diary files and extracts experiences, emotions, and truths.
"""

import os
import re
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv
from openai import AsyncOpenAI

from src.prompts.diary_extraction_prompt import DIARY_EXTRACTION_PROMPT

load_dotenv()

logger = logging.getLogger(__name__)

openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def parse_diary_filename(filename: str) -> Dict[str, str]:
    """
    Parse diary filename to extract UUID and date.
    
    Filename format: [UUID]-[YYYY-MM-DD-HH-MM-SS].md
    Example: [34B84EC6-BCB1-4652-9EFA-6BC0D9B17698]-[2026-01-04-13-01-20].md
    
    Returns:
        Dict with 'diary_id', 'date', 'datetime'
    """
    # Extract UUID and datetime from filename
    pattern = r'\[([A-F0-9-]+)\]-\[(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})\]\.md'
    match = re.match(pattern, filename, re.IGNORECASE)
    
    if not match:
        raise ValueError(f"Invalid diary filename format: {filename}")
    
    uuid = match.group(1)
    year, month, day, hour, minute, second = match.groups()[1:]
    
    date_str = f"{year}-{month}-{day}"
    datetime_str = f"{year}-{month}-{day}T{hour}:{minute}:{second}"
    
    return {
        "diary_id": uuid,
        "date": date_str,
        "datetime": datetime_str
    }


def load_diary(file_path: str) -> Dict[str, Any]:
    """
    Load a diary markdown file.
    
    Returns:
        Dict with 'diary_id', 'date', 'datetime', 'content'
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Diary file not found: {file_path}")
    
    # Parse filename for metadata
    metadata = parse_diary_filename(path.name)
    
    # Read content
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    
    return {
        "diary_id": metadata["diary_id"],
        "date": metadata["date"],
        "datetime": metadata["datetime"],
        "content": content
    }


async def extract_from_diary(
    diary_id: str,
    diary_date: str,
    content: str
) -> Dict[str, Any]:
    """
    Extract memories from a diary entry using LLM.
    
    Args:
        diary_id: Unique diary identifier (UUID from filename)
        diary_date: Date of diary entry (YYYY-MM-DD)
        content: The diary entry content
        
    Returns:
        Extracted data with experiences, emotions, truths, relationships
    """
    try:
        user_content = f"""DIARY ENTRY TO ANALYZE (Diary ID: {diary_id}, Date: {diary_date}):

{content}"""

        response = await openai_client.chat.completions.create(
            model="gpt-5.2",
            messages=[
                {
                    "role": "system",
                    "content": DIARY_EXTRACTION_PROMPT
                },
                {
                    "role": "user",
                    "content": user_content
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        extracted_data = json.loads(response.choices[0].message.content)
        
        # Add metadata
        extracted_data["diary_metadata"] = {
            "diary_id": diary_id,
            "diary_date": diary_date,
            "content_preview": content[:200] if content else ""
        }
        
        return extracted_data
        
    except Exception as e:
        logger.error(f"Error extracting from diary {diary_id}: {e}")
        return {
            "experiences": [],
            "emotions": [],
            "truths": [],
            "relationships": {},
            "diary_metadata": {
                "diary_id": diary_id,
                "diary_date": diary_date,
                "error": str(e)
            }
        }

