"""
Transcript database schema initialization and validation
"""
import logging
from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
from typing import Dict, Any

logger = logging.getLogger(__name__)


def create_transcript_indexes(db) -> None:
    """
    Create optimized indexes for transcript collection

    Args:
        db: MongoDB database instance
    """
    try:
        collection = db.transcripts

        # Primary index: Query transcripts by call, ordered by time
        collection.create_index(
            [("call_sid", ASCENDING), ("ts", ASCENDING)],
            name="idx_call_timestamp",
            background=True
        )
        logger.info("Created index: idx_call_timestamp")

        # Query transcripts by user
        collection.create_index(
            [("user_id", ASCENDING), ("ts", DESCENDING)],
            name="idx_user_timestamp",
            background=True,
            sparse=True  # user_id may not always be present
        )
        logger.info("Created index: idx_user_timestamp")

        # Query by speaker for a call
        collection.create_index(
            [("call_sid", ASCENDING), ("speaker", ASCENDING), ("ts", ASCENDING)],
            name="idx_call_speaker_timestamp",
            background=True
        )
        logger.info("Created index: idx_call_speaker_timestamp")

        # Full-text search on transcript text
        collection.create_index(
            [("text", TEXT)],
            name="idx_text_search",
            default_language="english",
            weights={"text": 10},
            background=True
        )
        logger.info("Created index: idx_text_search")

        # Filter by final vs interim
        collection.create_index(
            [("is_final", ASCENDING), ("created_at", DESCENDING)],
            name="idx_final_created",
            background=True,
            sparse=True
        )
        logger.info("Created index: idx_final_created")

        # Confidence filtering
        collection.create_index(
            [("confidence", ASCENDING)],
            name="idx_confidence",
            background=True,
            sparse=True  # Only index documents with confidence field
        )
        logger.info("Created index: idx_confidence")

        # Language filtering
        collection.create_index(
            [("language", ASCENDING), ("created_at", DESCENDING)],
            name="idx_language_created",
            background=True,
            sparse=True
        )
        logger.info("Created index: idx_language_created")

        # Compound index for analytics queries
        collection.create_index(
            [("created_at", DESCENDING), ("call_sid", ASCENDING)],
            name="idx_created_call",
            background=True
        )
        logger.info("Created index: idx_created_call")

        logger.info("All transcript indexes created successfully")

    except Exception as e:
        logger.error(f"Failed to create transcript indexes: {str(e)}")
        raise


def create_transcript_validation_schema() -> Dict[str, Any]:
    """
    Create MongoDB validation schema for transcripts collection

    Returns:
        Validation schema dictionary
    """
    return {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["call_sid", "speaker", "text", "ts", "created_at"],
            "properties": {
                "call_sid": {
                    "bsonType": "string",
                    "pattern": "^CA[0-9a-f]{32}$",
                    "description": "Twilio Call SID - required"
                },
                "user_id": {
                    "bsonType": "string",
                    "description": "User ObjectId reference (optional)"
                },
                "speaker": {
                    "bsonType": "string",
                    "enum": ["caller", "agent", "system", "unknown"],
                    "description": "Speaker identifier - required"
                },
                "text": {
                    "bsonType": "string",
                    "minLength": 1,
                    "maxLength": 10000,
                    "description": "Transcript text content - required"
                },
                "ts": {
                    "bsonType": "date",
                    "description": "Timestamp when spoken - required"
                },
                "confidence": {
                    "bsonType": ["double", "null"],
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "Confidence score 0.0-1.0"
                },
                "duration": {
                    "bsonType": ["double", "null"],
                    "minimum": 0,
                    "description": "Duration in seconds"
                },
                "start_offset": {
                    "bsonType": ["double", "null"],
                    "minimum": 0,
                    "description": "Start offset from call start (seconds)"
                },
                "end_offset": {
                    "bsonType": ["double", "null"],
                    "minimum": 0,
                    "description": "End offset from call start (seconds)"
                },
                "is_final": {
                    "bsonType": ["bool", "null"],
                    "description": "Final vs interim transcript"
                },
                "language": {
                    "bsonType": ["string", "null"],
                    "pattern": "^[a-z]{2}(-[A-Z]{2})?$",
                    "description": "Language code (e.g., en-US)"
                },
                "words": {
                    "bsonType": ["array", "null"],
                    "description": "Word-level transcript data",
                    "items": {
                        "bsonType": "object",
                        "required": ["word", "start", "end"],
                        "properties": {
                            "word": {
                                "bsonType": "string",
                                "description": "Word text"
                            },
                            "start": {
                                "bsonType": "double",
                                "description": "Start time (seconds)"
                            },
                            "end": {
                                "bsonType": "double",
                                "description": "End time (seconds)"
                            },
                            "confidence": {
                                "bsonType": ["double", "null"],
                                "minimum": 0.0,
                                "maximum": 1.0,
                                "description": "Word confidence"
                            },
                            "punctuated_word": {
                                "bsonType": ["string", "null"],
                                "description": "Word with punctuation"
                            }
                        }
                    }
                },
                "metadata": {
                    "bsonType": ["object", "null"],
                    "description": "Additional STT metadata",
                    "properties": {
                        "provider": {
                            "bsonType": ["string", "null"],
                            "enum": ["deepgram", "twilio", "google", "azure", null],
                            "description": "STT provider"
                        },
                        "model": {
                            "bsonType": ["string", "null"],
                            "description": "STT model used"
                        },
                        "speech_final": {
                            "bsonType": ["bool", "null"],
                            "description": "Deepgram speech_final flag"
                        },
                        "channel": {
                            "bsonType": ["int", "null"],
                            "description": "Audio channel"
                        }
                    }
                },
                "created_at": {
                    "bsonType": "date",
                    "description": "Database creation timestamp - required"
                },
                "indexed_at": {
                    "bsonType": ["date", "null"],
                    "description": "Search indexing timestamp"
                }
            }
        }
    }


def initialize_transcript_collection(db, enable_validation: bool = False) -> None:
    """
    Initialize transcripts collection with schema and indexes

    Args:
        db: MongoDB database instance
        enable_validation: Whether to enable schema validation (default: False)
    """
    try:
        collection_name = "transcripts"

        # Check if collection exists
        if collection_name in db.list_collection_names():
            logger.info(f"Collection '{collection_name}' already exists")
        else:
            logger.info(f"Creating collection '{collection_name}'")
            db.create_collection(collection_name)

        # Apply validation schema if enabled
        if enable_validation:
            logger.info("Applying validation schema to transcripts collection")
            db.command({
                "collMod": collection_name,
                "validator": create_transcript_validation_schema(),
                "validationLevel": "moderate",  # Don't validate on updates
                "validationAction": "warn"  # Log warnings instead of rejecting
            })

        # Create indexes
        create_transcript_indexes(db)

        logger.info(f"Transcripts collection initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize transcripts collection: {str(e)}")
        raise


def get_transcript_stats(db) -> Dict[str, Any]:
    """
    Get statistics about transcript collection

    Args:
        db: MongoDB database instance

    Returns:
        Dictionary with collection statistics
    """
    try:
        collection = db.transcripts

        # Get basic stats
        total_count = collection.count_documents({})

        # Get unique calls count
        unique_calls = len(collection.distinct("call_sid"))

        # Get language distribution
        language_pipeline = [
            {"$group": {"_id": "$language", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        language_dist = list(collection.aggregate(language_pipeline))

        # Get speaker distribution
        speaker_pipeline = [
            {"$group": {"_id": "$speaker", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        speaker_dist = list(collection.aggregate(speaker_pipeline))

        # Get average confidence
        avg_confidence_pipeline = [
            {"$match": {"confidence": {"$exists": True, "$ne": None}}},
            {"$group": {"_id": None, "avg_confidence": {"$avg": "$confidence"}}}
        ]
        avg_result = list(collection.aggregate(avg_confidence_pipeline))
        avg_confidence = avg_result[0]["avg_confidence"] if avg_result else None

        # Get collection size
        stats = db.command("collStats", "transcripts")
        size_mb = stats.get("size", 0) / (1024 * 1024)
        storage_size_mb = stats.get("storageSize", 0) / (1024 * 1024)

        return {
            "total_transcripts": total_count,
            "unique_calls": unique_calls,
            "avg_transcripts_per_call": total_count / unique_calls if unique_calls > 0 else 0,
            "languages": language_dist,
            "speakers": speaker_dist,
            "avg_confidence": round(avg_confidence, 4) if avg_confidence else None,
            "collection_size_mb": round(size_mb, 2),
            "storage_size_mb": round(storage_size_mb, 2),
            "indexes": stats.get("nindexes", 0)
        }

    except Exception as e:
        logger.error(f"Failed to get transcript stats: {str(e)}")
        return {}
