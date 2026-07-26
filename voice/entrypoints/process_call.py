"""
Entrypoint for processing a single call transcript.
Extracts memories and stores them in Neo4j.

Usage:
    python -m voice.entrypoints.process_call <transcript_path> <user_id> [--dry-run]
    
Example:
    python -m voice.entrypoints.process_call data/self-exploration-call/transcript-xxx.json user_001
    python -m voice.entrypoints.process_call data/self-exploration-call/transcript-xxx.json user_001 --dry-run
"""

import asyncio
import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from voice.src.memory.call_extractor import extract_from_call
from memora.memory.storage import MemoryStorage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_transcript(file_path: str) -> dict:
    """Load and validate a transcript JSON file."""
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Transcript file not found: {file_path}")
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Validate required fields
    required_fields = ["callId", "callDate", "messages"]
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing required field in transcript: {field}")
    
    return data


async def process_call(
    transcript_path: str,
    user_id: str,
    dry_run: bool = False
) -> dict:
    """
    Process a single call transcript: extract memories and store to Neo4j.
    
    Args:
        transcript_path: Path to the transcript JSON file
        user_id: User identifier
        dry_run: If True, extract but don't store to database
        
    Returns:
        Extracted data dict
    """
    # Load transcript
    logger.info(f"Loading transcript: {transcript_path}")
    transcript = load_transcript(transcript_path)
    
    call_id = transcript["callId"]
    call_date = transcript["callDate"]
    messages = transcript["messages"]
    
    logger.info(
        f"Processing call {call_id} "
        f"({len(messages)} messages, date: {call_date[:10]})"
    )
    
    # Extract memories
    logger.info("Extracting memories from conversation...")
    extracted_data = await extract_from_call(
        call_id=call_id,
        call_date=call_date,
        messages=messages
    )
    
    # Log extraction results
    exp_count = len(extracted_data.get("experiences", []))
    emo_count = len(extracted_data.get("emotions", []))
    truth_count = len(extracted_data.get("truths", []))
    
    logger.info(
        f"Extracted: {exp_count} experiences, "
        f"{emo_count} emotions, {truth_count} truths"
    )
    
    # Add first_synthesized to truths using call date
    date_only = call_date[:10] if call_date and len(call_date) >= 10 else call_date
    for truth in extracted_data.get("truths", []):
        if "first_synthesized" not in truth:
            truth["first_synthesized"] = date_only
    
    if dry_run:
        logger.info("Dry run mode - skipping database storage")
        
        # Save to output file
        output_dir = Path(__file__).parent.parent.parent / "data" / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"call_extracted_{timestamp}.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(extracted_data, f, indent=2)
        
        logger.info(f"Saved extracted data to: {output_file}")
        
        
        return extracted_data
    
    # Store to Neo4j
    logger.info("Storing memories to Neo4j...")
    storage = MemoryStorage()
    
    # Prepare data for storage - adapt to existing store_extracted_data format
    storage_data = {
        "experiences": extracted_data.get("experiences", []),
        "emotions": extracted_data.get("emotions", []),
        "truths": extracted_data.get("truths", []),
        "relationships": extracted_data.get("relationships", {}),
        "message_metadata": {
            "timestamp": call_date
        }
    }
    
    await storage.store_extracted_data(
        user_id=user_id,
        extracted_data=storage_data,
        call_id=call_id
    )
    
    logger.info(f"Successfully processed call {call_id}")
    
    return extracted_data


def main():
    parser = argparse.ArgumentParser(
        description="Process a call transcript and extract memories"
    )
    parser.add_argument(
        "transcript_path",
        help="Path to the transcript JSON file"
    )
    parser.add_argument(
        "user_id",
        help="User identifier"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract memories but don't store to database"
    )
    
    args = parser.parse_args()
    
    try:
        result = asyncio.run(
            process_call(
                transcript_path=args.transcript_path,
                user_id=args.user_id,
                dry_run=args.dry_run
            )
        )
        
        if not args.dry_run:
            print(f"\nProcessed successfully:")
            print(f"  Experiences: {len(result.get('experiences', []))}")
            print(f"  Emotions: {len(result.get('emotions', []))}")
            print(f"  Truths: {len(result.get('truths', []))}")
            
    except Exception as e:
        logger.error(f"Failed to process call: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

