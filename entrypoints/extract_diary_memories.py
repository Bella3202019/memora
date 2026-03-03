"""
Entrypoint for extracting memories from diary entries and storing them in Neo4j.

Usage:
    # Single file
    python -m entrypoints.extract_diary_memories <diary_path> <user_id> [--dry-run]
    
    # All files in directory
    python -m entrypoints.extract_diary_memories --dir <diary_folder> <user_id> [--dry-run]

Example:
    python -m entrypoints.extract_diary_memories "/path/to/diary.md" user_001
    python -m entrypoints.extract_diary_memories --dir "/path/to/diaries/" user_001 --dry-run
"""

import asyncio
import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Set, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.memory.diary_extractor import load_diary, extract_from_diary
from src.memory.storage import MemoryStorage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
MIN_DIARY_CONTENT_LENGTH = 10
PROCESSED_LOG_FILE = Path(__file__).parent.parent / "data" / "processed_diaries.txt"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "output"


def load_processed_diaries() -> Set[str]:
    """Return the set of already-processed diary filenames."""
    if not PROCESSED_LOG_FILE.exists():
        return set()
    return set(PROCESSED_LOG_FILE.read_text().splitlines())


def mark_diary_as_processed(filename: str) -> None:
    """Append a diary filename to the processed log."""
    PROCESSED_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROCESSED_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(filename + "\n")
    logger.info(f"Marked as processed: {filename}")


def get_diary_files(directory: str) -> List[Path]:
    """
    Get all diary markdown files from a directory, sorted by date.
    
    Diary files must match the pattern: [UUID]-[YYYY-MM-DD-HH-MM-SS].md
    """
    dir_path = Path(directory)
    
    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    
    # Get all .md files matching the diary pattern
    diary_files = [
        f for f in dir_path.glob("*.md")
        if f.name.startswith("[") and "]-[" in f.name
    ]
    
    # Sort by filename (which contains the date)
    diary_files.sort(key=lambda x: x.name)
    
    return diary_files


def save_extracted_data(extracted_data: Dict[str, Any], diary_date: str) -> Path:
    """Save extracted data to JSON file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"diary_extracted_{diary_date}.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(extracted_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved extracted data to: {output_file}")
    return output_file


async def extract_memories_from_diary(
    diary_path: str,
    user_id: str,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Extract memories from a single diary file and optionally store to Neo4j.
    
    Args:
        diary_path: Path to the diary markdown file
        user_id: User identifier
        dry_run: If True, extract but don't store to database
        
    Returns:
        Extracted data dict with experiences, emotions, truths, and relationships
    """
    # Load diary
    logger.info(f"Loading diary: {diary_path}")
    diary = load_diary(diary_path)
    
    diary_id = diary["diary_id"]
    diary_date = diary["date"]
    content = diary["content"]
    
    # Skip empty or too short diaries
    if not content or len(content.strip()) < MIN_DIARY_CONTENT_LENGTH:
        logger.warning(f"Skipping empty or too short diary: {diary_path}")
        return {"skipped": True, "reason": "empty or too short"}
    
    logger.info(
        f"Processing diary {diary_id[:8]}... "
        f"(date: {diary_date}, {len(content)} chars)"
    )
    
    # Extract memories
    logger.info("Extracting memories from diary...")
    extracted_data = await extract_from_diary(
        diary_id=diary_id,
        diary_date=diary_date,
        content=content
    )
    
    # Log extraction results
    exp_count = len(extracted_data.get("experiences", []))
    emo_count = len(extracted_data.get("emotions", []))
    truth_count = len(extracted_data.get("truths", []))
    
    logger.info(
        f"Extracted: {exp_count} experiences, "
        f"{emo_count} emotions, {truth_count} truths"
    )
    
    # Add first_synthesized to truths using diary date
    for truth in extracted_data.get("truths", []):
        if "first_synthesized" not in truth:
            truth["first_synthesized"] = diary_date
    
    # Always save extracted data to JSON
    save_extracted_data(extracted_data, diary_date)

    if dry_run:
        logger.info("Dry run mode - skipping database storage")
        return extracted_data
    
    # Store to Neo4j
    logger.info("Storing memories to Neo4j...")
    storage = MemoryStorage()
    
    # Create ISO timestamp from diary date for storage
    timestamp = f"{diary_date}T00:00:00Z"
    
    storage_data = {
        "experiences": extracted_data.get("experiences", []),
        "emotions": extracted_data.get("emotions", []),
        "truths": extracted_data.get("truths", []),
        "relationships": extracted_data.get("relationships", {}),
        "message_metadata": {
            "timestamp": timestamp
        }
    }
    
    await storage.store_extracted_data(
        user_id=user_id,
        extracted_data=storage_data,
        call_id=diary_id  # Using call_id field to store diary_id
    )

    mark_diary_as_processed(Path(diary_path).name)
    logger.info(f"Successfully processed diary {diary_id[:8]}...")
    
    return extracted_data


async def extract_memories_from_all_diaries(
    directory: str,
    user_id: str,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Extract memories from all diary files in a directory.
    
    Args:
        directory: Path to directory containing diary files
        user_id: User identifier
        dry_run: If True, extract but don't store to database
        
    Returns:
        Summary dict with processing results
    """
    diary_files = get_diary_files(directory)
    
    if not diary_files:
        logger.warning(f"No diary files found in: {directory}")
        return {"total": 0, "processed": 0, "skipped": 0, "errors": 0, "details": []}
    
    logger.info(f"Found {len(diary_files)} diary files to process")

    processed = load_processed_diaries()

    results: Dict[str, Any] = {
        "total": len(diary_files),
        "processed": 0,
        "skipped": 0,
        "errors": 0,
        "details": []
    }

    for i, diary_path in enumerate(diary_files, 1):
        if diary_path.name in processed:
            logger.info(f"Skipping already processed: {diary_path.name}")
            results["skipped"] += 1
            results["details"].append({
                "file": diary_path.name,
                "status": "skipped",
                "reason": "already processed"
            })
            continue

        logger.info(f"\n--- Processing {i}/{len(diary_files)}: {diary_path.name} ---")
        
        try:
            result = await extract_memories_from_diary(
                diary_path=str(diary_path),
                user_id=user_id,
                dry_run=dry_run
            )
            
            if result.get("skipped"):
                results["skipped"] += 1
            else:
                results["processed"] += 1
                
            results["details"].append({
                "file": diary_path.name,
                "status": "skipped" if result.get("skipped") else "processed",
                "experiences": len(result.get("experiences", [])),
                "emotions": len(result.get("emotions", [])),
                "truths": len(result.get("truths", []))
            })
            
        except Exception as e:
            logger.error(f"Error processing {diary_path.name}: {e}")
            results["errors"] += 1
            results["details"].append({
                "file": diary_path.name,
                "status": "error",
                "error": str(e)
            })
    
    return results


def main() -> None:
    """Main entry point for diary memory extraction."""
    parser = argparse.ArgumentParser(
        description="Extract memories from diary entries and store in Neo4j"
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Path to diary file (or use --dir for directory)"
    )
    parser.add_argument(
        "user_id",
        help="User identifier"
    )
    parser.add_argument(
        "--dir",
        dest="directory",
        help="Process all diary files in this directory"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract memories but don't store to database"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.path and not args.directory:
        parser.error("Either provide a diary path or use --dir for batch processing")
    
    if args.path and args.directory:
        parser.error("Cannot use both path and --dir at the same time")
    
    try:
        if args.directory:
            # Batch processing
            results = asyncio.run(
                extract_memories_from_all_diaries(
                    directory=args.directory,
                    user_id=args.user_id,
                    dry_run=args.dry_run
                )
            )
            
            print(f"\n=== Processing Complete ===")
            print(f"Total files: {results['total']}")
            print(f"Processed: {results['processed']}")
            print(f"Skipped: {results['skipped']}")
            print(f"Errors: {results['errors']}")
            
        else:
            # Single file processing
            result = asyncio.run(
                extract_memories_from_diary(
                    diary_path=args.path,
                    user_id=args.user_id,
                    dry_run=args.dry_run
                )
            )
            
            if not args.dry_run and not result.get("skipped"):
                print(f"\nProcessed successfully:")
                print(f"  Experiences: {len(result.get('experiences', []))}")
                print(f"  Emotions: {len(result.get('emotions', []))}")
                print(f"  Truths: {len(result.get('truths', []))}")
            
    except Exception as e:
        logger.error(f"Failed to process: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
