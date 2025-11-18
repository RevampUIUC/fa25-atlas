# Transcript Storage and Retrieval - Usage Guide

This guide explains how to use the transcript storage system in the Atlas application.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Storing Transcripts](#storing-transcripts)
4. [Querying Transcripts](#querying-transcripts)
5. [Formatting and Export](#formatting-and-export)
6. [Integration with Deepgram](#integration-with-deepgram)
7. [Best Practices](#best-practices)
8. [API Examples](#api-examples)

## Overview

The transcript storage system provides:
- MongoDB-based storage with schema validation
- Multiple serialization formats (Database, JSON, Export)
- Powerful query capabilities (by call, user, full-text search)
- Multiple output formats (Text, HTML, Markdown)
- Automatic indexing for high-performance queries
- Support for word-level transcript data

## Quick Start

### 1. Initialize the System

The transcript collection is automatically initialized when the application starts:

```python
# In app/main.py startup event
from app.transcript_schema import initialize_transcript_collection

@app.on_event("startup")
async def startup_event():
    # ... database initialization ...

    # Initialize transcript collection
    initialize_transcript_collection(db.db)
```

### 2. Store a Transcript

```python
from app.transcript_utils import TranscriptSerializer

# Store a transcript from Deepgram
transcript_data = TranscriptSerializer.to_database(
    call_sid="CA1234567890abcdef",
    speaker="caller",
    text="Hello, I need help with my account.",
    ts=datetime.utcnow(),
    confidence=0.98,
    user_id="507f191e810c19729de860ea"
)

db.db.transcripts.insert_one(transcript_data)
```

### 3. Retrieve Transcripts

```python
from app.transcript_utils import TranscriptQuery

# Get all transcripts for a call
transcripts = TranscriptQuery.by_call(
    db.db,
    call_sid="CA1234567890abcdef"
)

# Format as text
from app.transcript_utils import TranscriptFormatter
text_output = TranscriptFormatter.to_text(transcripts)
print(text_output)
```

## Storing Transcripts

### From Deepgram Real-time Transcription

When receiving transcript events from Deepgram:

```python
from app.transcript_utils import TranscriptSerializer

def on_transcript_received(call_sid, deepgram_result, user_id):
    """Handle incoming transcript from Deepgram"""

    # Convert Deepgram format to database format
    transcript_doc = TranscriptSerializer.from_deepgram(
        call_sid=call_sid,
        deepgram_result=deepgram_result,
        user_id=user_id
    )

    # Save to database
    db.db.transcripts.insert_one(transcript_doc)

    # Log only final transcripts
    if transcript_doc.get("is_final"):
        logger.info(f"Saved final transcript for call {call_sid}: {transcript_doc['text']}")
```

### Manual Storage

For storing transcripts from other sources:

```python
from app.transcript_utils import TranscriptSerializer
from datetime import datetime

transcript_data = TranscriptSerializer.to_database(
    call_sid="CA1234567890abcdef",
    speaker="agent",
    text="I can help you with that.",
    ts=datetime.utcnow(),
    confidence=0.99,
    user_id="507f191e810c19729de860ea",
    duration=2.5,
    start_offset=10.0,
    end_offset=12.5,
    is_final=True,
    language="en-US",
    words=[
        {
            "word": "I",
            "start": 0.0,
            "end": 0.1,
            "confidence": 0.99
        },
        {
            "word": "can",
            "start": 0.2,
            "end": 0.4,
            "confidence": 0.99
        },
        # ... more words
    ],
    metadata={
        "provider": "deepgram",
        "model": "nova-2"
    }
)

db.db.transcripts.insert_one(transcript_data)
```

## Querying Transcripts

### By Call SID

Retrieve all transcripts for a specific call:

```python
from app.transcript_utils import TranscriptQuery

# Get all transcripts (including interim)
all_transcripts = TranscriptQuery.by_call(
    db.db,
    call_sid="CA1234567890abcdef",
    final_only=False
)

# Get only final transcripts (default)
final_transcripts = TranscriptQuery.by_call(
    db.db,
    call_sid="CA1234567890abcdef"
)

# Filter by minimum confidence
high_confidence = TranscriptQuery.by_call(
    db.db,
    call_sid="CA1234567890abcdef",
    min_confidence=0.95
)
```

### By User ID

Retrieve transcripts across all calls for a user:

```python
from datetime import datetime, timedelta

# Get recent transcripts for a user
user_transcripts = TranscriptQuery.by_user(
    db.db,
    user_id="507f191e810c19729de860ea",
    start_date=datetime.utcnow() - timedelta(days=7),
    end_date=datetime.utcnow(),
    final_only=True
)
```

### Full-Text Search

Search transcripts by keyword or phrase:

```python
# Search across all calls
search_results = TranscriptQuery.search_text(
    db.db,
    search_query="password reset"
)

# Search within a specific call
call_search = TranscriptQuery.search_text(
    db.db,
    search_query="account number",
    call_sid="CA1234567890abcdef"
)

# Access search results
for result in search_results:
    print(f"Score: {result['score']:.2f}")
    print(f"Call: {result['call_sid']}")
    print(f"Speaker: {result['speaker']}")
    print(f"Text: {result['text']}")
    print(f"Time: {result['ts']}")
    print("---")
```

### Get Call Summary

Get aggregated statistics for a call:

```python
summary = TranscriptQuery.get_call_summary(
    db.db,
    call_sid="CA1234567890abcdef"
)

print(f"Total utterances: {summary['total_utterances']}")
print(f"Total words: {summary['total_words']}")
print(f"Average confidence: {summary['avg_confidence']:.2f}")
print(f"Duration: {summary['total_duration']:.1f}s")
print(f"Speakers: {', '.join(summary['speakers'])}")
print(f"Languages: {', '.join(summary['languages'])}")
```

## Formatting and Export

### Text Format

Plain text format with timestamps:

```python
from app.transcript_utils import TranscriptFormatter

transcripts = TranscriptQuery.by_call(db.db, call_sid)

# With timestamps (default)
text_with_time = TranscriptFormatter.to_text(
    transcripts,
    include_timestamps=True
)

# Without timestamps
text_only = TranscriptFormatter.to_text(
    transcripts,
    include_timestamps=False
)

# Save to file
with open("transcript.txt", "w") as f:
    f.write(text_with_time)
```

### HTML Format

HTML format with CSS classes for styling:

```python
html_output = TranscriptFormatter.to_html(transcripts)

# Wrap in full HTML document
full_html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Call Transcript</title>
    <style>
        .transcript {{ font-family: Arial, sans-serif; }}
        .utterance {{ margin: 10px 0; }}
        .timestamp {{ color: #666; font-size: 0.9em; }}
        .speaker {{ font-weight: bold; }}
        .speaker-caller {{ color: #2196F3; }}
        .speaker-agent {{ color: #4CAF50; }}
        .speaker-system {{ color: #FF9800; }}
        .text {{ margin-left: 10px; }}
    </style>
</head>
<body>
    {html_output}
</body>
</html>
"""

with open("transcript.html", "w") as f:
    f.write(full_html)
```

### Markdown Format

Markdown format for documentation:

```python
markdown_output = TranscriptFormatter.to_markdown(
    transcripts,
    title="Call Transcript - January 10, 2025"
)

with open("transcript.md", "w") as f:
    f.write(markdown_output)
```

### JSON Export Format

Full export with call metadata:

```python
from app.transcript_utils import TranscriptSerializer

# Get all transcripts for the call
transcripts = list(TranscriptQuery.by_call(db.db, call_sid))

# Get call metadata
call = db.get_call_by_twilio_sid(call_sid)

call_metadata = {
    "call_sid": call_sid,
    "user_id": call.get("user_id"),
    "user_name": "John Doe",
    "user_phone": "+15551234567",
    "started_at": call.get("created_at"),
    "ended_at": call.get("ended_at"),
    "duration_sec": call.get("duration"),
    "status": call.get("status")
}

# Create export format
export_data = TranscriptSerializer.to_export_format(
    call_sid=call_sid,
    transcripts=transcripts,
    call_metadata=call_metadata
)

# Save to file
import json
with open(f"transcript_{call_sid}.json", "w") as f:
    json.dump(export_data, f, indent=2, default=str)
```

## Integration with Deepgram

### Setting up Real-time Transcription

The Deepgram integration automatically saves transcripts to the database:

```python
from app.deepgram_client import TranscriptionSession
from app.transcript_utils import TranscriptSerializer

async def start_call_transcription(call_sid, user_id):
    """Start transcribing a call"""

    def on_transcript(transcript_text, metadata):
        """Callback when transcript is received"""

        # Convert Deepgram result to database format
        deepgram_result = {
            "channel": {
                "alternatives": [{
                    "transcript": transcript_text,
                    "confidence": metadata.get("confidence", 0.0),
                    "words": metadata.get("words", [])
                }]
            },
            "is_final": metadata.get("is_final", False),
            "duration": metadata.get("duration"),
            "start": metadata.get("start"),
            "metadata": {
                "model_info": {
                    "name": metadata.get("model", "nova-2")
                }
            }
        }

        # Save to database
        transcript_doc = TranscriptSerializer.from_deepgram(
            call_sid=call_sid,
            deepgram_result=deepgram_result,
            user_id=user_id
        )

        db.db.transcripts.insert_one(transcript_doc)

    def on_error(error_message):
        """Callback for errors"""
        logger.error(f"Transcription error for call {call_sid}: {error_message}")

    # Create transcription session
    session = TranscriptionSession(
        call_sid=call_sid,
        user_id=user_id,
        on_transcript=on_transcript,
        on_error=on_error
    )

    await session.start()
    return session
```

## Best Practices

### Performance Optimization

1. **Query only what you need**:
   ```python
   # Good - query only final transcripts
   transcripts = TranscriptQuery.by_call(db.db, call_sid, final_only=True)

   # Avoid - querying all interim transcripts unnecessarily
   transcripts = TranscriptQuery.by_call(db.db, call_sid, final_only=False)
   ```

2. **Use indexes effectively**:
   ```python
   # Queries that use indexes (fast):
   - By call_sid + timestamp
   - By user_id + timestamp
   - By call_sid + speaker + timestamp
   - Text search queries

   # Queries that don't use indexes (slow):
   - Filtering by arbitrary fields without indexes
   ```

3. **Paginate large result sets**:
   ```python
   from datetime import datetime, timedelta

   # Query in batches by date range
   page_size = 1000
   start_date = datetime.utcnow() - timedelta(days=1)

   cursor = db.db.transcripts.find({
       "call_sid": call_sid,
       "ts": {"$gte": start_date}
   }).limit(page_size)
   ```

### Storage Optimization

1. **Store only final transcripts for long-term**:
   ```python
   # Delete interim transcripts after call ends
   db.db.transcripts.delete_many({
       "call_sid": call_sid,
       "is_final": False
   })
   ```

2. **Use TTL index for automatic cleanup**:
   ```python
   # Already configured in transcript_schema.py
   # Transcripts expire after 90 days (configurable)
   ```

3. **Enable compression** (MongoDB configuration):
   ```yaml
   # In MongoDB config
   storage:
     engine: wiredTiger
     wiredTiger:
       collectionConfig:
         blockCompressor: zstd
   ```

### Data Quality

1. **Filter by confidence**:
   ```python
   # Only store high-confidence transcripts
   if confidence >= 0.85:
       db.db.transcripts.insert_one(transcript_doc)
   ```

2. **Validate speaker labels**:
   ```python
   VALID_SPEAKERS = ["caller", "agent", "system"]

   if speaker not in VALID_SPEAKERS:
       speaker = "unknown"
   ```

3. **Handle missing data gracefully**:
   ```python
   transcript_data = TranscriptSerializer.to_database(
       call_sid=call_sid,
       speaker=speaker or "unknown",
       text=text or "",
       ts=ts or datetime.utcnow(),
       confidence=confidence if confidence is not None else 0.0
   )
   ```

## API Examples

### Creating a Transcript API Endpoint

```python
from fastapi import FastAPI, HTTPException, Query
from app.transcript_utils import TranscriptQuery, TranscriptFormatter
from app.models import TranscriptResponse

@app.get("/calls/{call_sid}/transcript")
async def get_call_transcript(
    call_sid: str,
    format: str = Query("json", regex="^(json|text|html|markdown)$"),
    final_only: bool = True,
    min_confidence: float = Query(None, ge=0.0, le=1.0)
):
    """Get transcript for a call in various formats"""

    # Query transcripts
    transcripts = TranscriptQuery.by_call(
        db.db,
        call_sid=call_sid,
        final_only=final_only,
        min_confidence=min_confidence
    )

    if not transcripts:
        raise HTTPException(
            status_code=404,
            detail=f"No transcripts found for call {call_sid}"
        )

    # Format based on request
    if format == "text":
        content = TranscriptFormatter.to_text(transcripts)
        return Response(content=content, media_type="text/plain")

    elif format == "html":
        content = TranscriptFormatter.to_html(transcripts)
        return Response(content=content, media_type="text/html")

    elif format == "markdown":
        content = TranscriptFormatter.to_markdown(transcripts)
        return Response(content=content, media_type="text/markdown")

    else:  # json
        return {"transcripts": transcripts}


@app.get("/calls/{call_sid}/transcript/export")
async def export_call_transcript(call_sid: str):
    """Export complete call transcript with metadata"""

    # Get transcripts
    transcripts = list(TranscriptQuery.by_call(db.db, call_sid))

    if not transcripts:
        raise HTTPException(
            status_code=404,
            detail=f"No transcripts found for call {call_sid}"
        )

    # Get call metadata
    call = db.get_call_by_twilio_sid(call_sid)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    # Get user details
    user = db.get_user(call.get("user_id"))

    call_metadata = {
        "call_sid": call_sid,
        "user_id": call.get("user_id"),
        "user_name": user.get("name") if user else None,
        "user_phone": call.get("to_number"),
        "started_at": call.get("created_at"),
        "ended_at": call.get("ended_at"),
        "duration_sec": call.get("duration"),
        "status": call.get("status")
    }

    # Create export
    export_data = TranscriptSerializer.to_export_format(
        call_sid=call_sid,
        transcripts=transcripts,
        call_metadata=call_metadata
    )

    return export_data


@app.get("/transcripts/search")
async def search_transcripts(
    query: str = Query(..., min_length=2),
    call_sid: str = None,
    limit: int = Query(50, ge=1, le=500)
):
    """Search transcripts by text"""

    results = TranscriptQuery.search_text(
        db.db,
        search_query=query,
        call_sid=call_sid
    )

    # Limit results
    results = results[:limit]

    return {
        "query": query,
        "total_results": len(results),
        "results": results
    }


@app.get("/calls/{call_sid}/summary")
async def get_call_summary(call_sid: str):
    """Get summary statistics for a call's transcripts"""

    summary = TranscriptQuery.get_call_summary(db.db, call_sid)

    if summary["total_utterances"] == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No transcripts found for call {call_sid}"
        )

    return summary
```

### Background Task for Saving Transcripts

```python
from fastapi import BackgroundTasks

async def save_transcript_background(
    call_sid: str,
    speaker: str,
    text: str,
    timestamp: datetime,
    confidence: float,
    user_id: str,
    **kwargs
):
    """Background task to save transcript without blocking"""
    try:
        transcript_data = TranscriptSerializer.to_database(
            call_sid=call_sid,
            speaker=speaker,
            text=text,
            ts=timestamp,
            confidence=confidence,
            user_id=user_id,
            **kwargs
        )

        db.db.transcripts.insert_one(transcript_data)
        logger.info(f"Saved transcript for call {call_sid}")

    except Exception as e:
        logger.error(f"Failed to save transcript: {str(e)}")


@app.post("/transcripts")
async def create_transcript(
    transcript: TranscriptCreate,
    background_tasks: BackgroundTasks
):
    """Create a new transcript (saves in background)"""

    # Enqueue save operation
    background_tasks.add_task(
        save_transcript_background,
        call_sid=transcript.call_sid,
        speaker=transcript.speaker,
        text=transcript.text,
        timestamp=transcript.timestamp,
        confidence=transcript.confidence,
        user_id=transcript.user_id
    )

    return {"status": "queued", "message": "Transcript save queued"}
```

## Troubleshooting

### Common Issues

1. **Schema validation errors**:
   ```
   Error: Document failed validation
   ```

   **Solution**: Ensure all required fields are present:
   - call_sid (string)
   - speaker (string)
   - text (string)
   - ts (datetime)
   - created_at (datetime)

2. **Slow queries**:
   ```
   Query taking >1 second
   ```

   **Solution**:
   - Check indexes are created: `db.transcripts.getIndexes()`
   - Use indexed fields in queries
   - Add `final_only=True` to filter interim transcripts

3. **Storage growing too large**:
   ```
   Transcript collection > 10GB
   ```

   **Solution**:
   - Enable TTL index to auto-delete old transcripts
   - Delete interim transcripts: `db.transcripts.deleteMany({is_final: false})`
   - Enable MongoDB compression
   - Consider archiving old transcripts

### Debug Mode

Enable detailed logging for transcript operations:

```python
import logging

# Set transcript logger to DEBUG
logging.getLogger("app.transcript_utils").setLevel(logging.DEBUG)
logging.getLogger("app.transcript_schema").setLevel(logging.DEBUG)
```

## Additional Resources

- [Transcript Schema Documentation](TRANSCRIPT_SCHEMA.md)
- [Deepgram Integration Guide](DEEPGRAM_INTEGRATION.md)
- [MongoDB Text Search Documentation](https://docs.mongodb.com/manual/text-search/)
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
