# Transcript Storage Schema

This document defines the JSON schema and database structure for storing call transcripts with real-time speech-to-text data.

## Overview

The transcript storage system is designed to:
- Store real-time transcription data from Deepgram
- Link transcripts to calls and users
- Support speaker diarization
- Enable efficient querying and analysis
- Scale to handle high call volumes
- Support full-text search

## JSON Schema

### Transcript Document Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Call Transcript",
  "description": "Real-time speech-to-text transcript for a call",
  "type": "object",
  "required": ["call_sid", "speaker", "text", "ts"],
  "properties": {
    "_id": {
      "type": "string",
      "description": "MongoDB ObjectId (auto-generated)",
      "pattern": "^[0-9a-fA-F]{24}$"
    },
    "call_sid": {
      "type": "string",
      "description": "Twilio Call SID",
      "pattern": "^CA[0-9a-f]{32}$",
      "index": true
    },
    "user_id": {
      "type": "string",
      "description": "User ID (links to users collection)",
      "pattern": "^[0-9a-fA-F]{24}$",
      "index": true
    },
    "speaker": {
      "type": "string",
      "description": "Speaker identifier",
      "enum": ["caller", "agent", "system", "unknown"],
      "default": "caller"
    },
    "text": {
      "type": "string",
      "description": "Transcribed text content",
      "minLength": 1,
      "maxLength": 10000
    },
    "ts": {
      "type": "string",
      "format": "date-time",
      "description": "Timestamp when text was spoken (ISO 8601)"
    },
    "confidence": {
      "type": "number",
      "description": "Transcription confidence score (0.0-1.0)",
      "minimum": 0.0,
      "maximum": 1.0
    },
    "duration": {
      "type": "number",
      "description": "Duration of the utterance in seconds",
      "minimum": 0
    },
    "start_offset": {
      "type": "number",
      "description": "Start time offset from call start (seconds)",
      "minimum": 0
    },
    "end_offset": {
      "type": "number",
      "description": "End time offset from call start (seconds)",
      "minimum": 0
    },
    "is_final": {
      "type": "boolean",
      "description": "Whether this is a final transcript (vs interim)",
      "default": true
    },
    "language": {
      "type": "string",
      "description": "Detected or specified language code",
      "pattern": "^[a-z]{2}(-[A-Z]{2})?$",
      "default": "en-US"
    },
    "words": {
      "type": "array",
      "description": "Word-level transcript data",
      "items": {
        "$ref": "#/definitions/word"
      }
    },
    "metadata": {
      "type": "object",
      "description": "Additional metadata from STT provider",
      "properties": {
        "provider": {
          "type": "string",
          "enum": ["deepgram", "twilio", "google", "azure"],
          "default": "deepgram"
        },
        "model": {
          "type": "string",
          "description": "STT model used",
          "example": "nova-2"
        },
        "speech_final": {
          "type": "boolean",
          "description": "Deepgram speech_final flag"
        },
        "channel": {
          "type": "integer",
          "description": "Audio channel (for multi-channel)"
        }
      }
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "description": "When transcript was created in database"
    },
    "indexed_at": {
      "type": "string",
      "format": "date-time",
      "description": "When transcript was indexed for search"
    }
  },
  "definitions": {
    "word": {
      "type": "object",
      "required": ["word", "start", "end"],
      "properties": {
        "word": {
          "type": "string",
          "description": "The word text"
        },
        "start": {
          "type": "number",
          "description": "Word start time (seconds from utterance start)"
        },
        "end": {
          "type": "number",
          "description": "Word end time (seconds from utterance start)"
        },
        "confidence": {
          "type": "number",
          "description": "Confidence for this word",
          "minimum": 0.0,
          "maximum": 1.0
        },
        "punctuated_word": {
          "type": "string",
          "description": "Word with punctuation applied"
        }
      }
    }
  }
}
```

### Sample Transcript Document

```json
{
  "_id": "507f1f77bcf86cd799439011",
  "call_sid": "CA1234567890abcdef1234567890abcdef",
  "user_id": "507f191e810c19729de860ea",
  "speaker": "caller",
  "text": "Hello, I need help with my account.",
  "ts": "2025-01-10T14:23:45.123Z",
  "confidence": 0.98,
  "duration": 2.5,
  "start_offset": 5.2,
  "end_offset": 7.7,
  "is_final": true,
  "language": "en-US",
  "words": [
    {
      "word": "Hello",
      "start": 0.0,
      "end": 0.4,
      "confidence": 0.99,
      "punctuated_word": "Hello,"
    },
    {
      "word": "I",
      "start": 0.5,
      "end": 0.6,
      "confidence": 0.97
    },
    {
      "word": "need",
      "start": 0.7,
      "end": 0.9,
      "confidence": 0.98
    },
    {
      "word": "help",
      "start": 1.0,
      "end": 1.3,
      "confidence": 0.99
    },
    {
      "word": "with",
      "start": 1.4,
      "end": 1.6,
      "confidence": 0.98
    },
    {
      "word": "my",
      "start": 1.7,
      "end": 1.9,
      "confidence": 0.97
    },
    {
      "word": "account",
      "start": 2.0,
      "end": 2.5,
      "confidence": 0.99,
      "punctuated_word": "account."
    }
  ],
  "metadata": {
    "provider": "deepgram",
    "model": "nova-2",
    "speech_final": true,
    "channel": 0
  },
  "created_at": "2025-01-10T14:23:45.500Z",
  "indexed_at": "2025-01-10T14:23:46.000Z"
}
```

## MongoDB Schema

### Collection: `transcripts`

```javascript
// MongoDB schema definition
db.createCollection("transcripts", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["call_sid", "speaker", "text", "ts", "created_at"],
      properties: {
        call_sid: {
          bsonType: "string",
          pattern: "^CA[0-9a-f]{32}$",
          description: "Twilio Call SID - required"
        },
        user_id: {
          bsonType: "string",
          description: "User ObjectId reference"
        },
        speaker: {
          bsonType: "string",
          enum: ["caller", "agent", "system", "unknown"],
          description: "Speaker identifier"
        },
        text: {
          bsonType: "string",
          minLength: 1,
          maxLength: 10000,
          description: "Transcript text content"
        },
        ts: {
          bsonType: "date",
          description: "Timestamp when spoken"
        },
        confidence: {
          bsonType: "double",
          minimum: 0.0,
          maximum: 1.0,
          description: "Confidence score"
        },
        duration: {
          bsonType: "double",
          minimum: 0,
          description: "Duration in seconds"
        },
        start_offset: {
          bsonType: "double",
          minimum: 0,
          description: "Start offset from call start"
        },
        end_offset: {
          bsonType: "double",
          minimum: 0,
          description: "End offset from call start"
        },
        is_final: {
          bsonType: "bool",
          description: "Final vs interim transcript"
        },
        language: {
          bsonType: "string",
          pattern: "^[a-z]{2}(-[A-Z]{2})?$",
          description: "Language code"
        },
        words: {
          bsonType: "array",
          description: "Word-level data",
          items: {
            bsonType: "object",
            required: ["word", "start", "end"],
            properties: {
              word: { bsonType: "string" },
              start: { bsonType: "double" },
              end: { bsonType: "double" },
              confidence: { bsonType: "double" },
              punctuated_word: { bsonType: "string" }
            }
          }
        },
        metadata: {
          bsonType: "object",
          properties: {
            provider: {
              bsonType: "string",
              enum: ["deepgram", "twilio", "google", "azure"]
            },
            model: { bsonType: "string" },
            speech_final: { bsonType: "bool" },
            channel: { bsonType: "int" }
          }
        },
        created_at: {
          bsonType: "date",
          description: "Database creation timestamp"
        },
        indexed_at: {
          bsonType: "date",
          description: "Search indexing timestamp"
        }
      }
    }
  }
});
```

### Indexes for Performance

```javascript
// Primary index: Query transcripts by call
db.transcripts.createIndex(
  { "call_sid": 1, "ts": 1 },
  { name: "idx_call_timestamp" }
);

// Query transcripts by user
db.transcripts.createIndex(
  { "user_id": 1, "ts": -1 },
  { name: "idx_user_timestamp" }
);

// Search by speaker
db.transcripts.createIndex(
  { "call_sid": 1, "speaker": 1, "ts": 1 },
  { name: "idx_call_speaker_timestamp" }
);

// Full-text search on transcript text
db.transcripts.createIndex(
  { "text": "text" },
  {
    name: "idx_text_search",
    default_language: "english",
    weights: { text: 10 }
  }
);

// Compound index for filtering
db.transcripts.createIndex(
  { "is_final": 1, "created_at": -1 },
  { name: "idx_final_created" }
);

// TTL index for old transcripts (optional - auto-delete after 90 days)
db.transcripts.createIndex(
  { "created_at": 1 },
  {
    name: "idx_ttl_cleanup",
    expireAfterSeconds: 7776000  // 90 days
  }
);

// Index for confidence filtering
db.transcripts.createIndex(
  { "confidence": 1 },
  {
    name: "idx_confidence",
    sparse: true  // Only index documents with confidence field
  }
);
```

## Aggregate Schema

### Full Call Transcript

For presenting complete call transcripts, create an aggregated view:

```json
{
  "_id": "507f191e810c19729de860ea",
  "call_sid": "CA1234567890abcdef1234567890abcdef",
  "user_id": "507f191e810c19729de860ea",
  "user_name": "John Doe",
  "user_phone": "+15551234567",
  "call_started_at": "2025-01-10T14:20:00.000Z",
  "call_ended_at": "2025-01-10T14:25:30.000Z",
  "call_duration_sec": 330,
  "transcript_count": 45,
  "total_words": 423,
  "languages": ["en-US"],
  "speakers": ["caller", "agent"],
  "average_confidence": 0.96,
  "transcripts": [
    {
      "speaker": "system",
      "text": "This call may be recorded for quality assurance...",
      "ts": "2025-01-10T14:20:05.000Z",
      "offset": 5.0
    },
    {
      "speaker": "caller",
      "text": "Hello, I need help with my account.",
      "ts": "2025-01-10T14:20:10.000Z",
      "offset": 10.0,
      "confidence": 0.98
    },
    {
      "speaker": "agent",
      "text": "Of course, I'd be happy to help. May I have your account number?",
      "ts": "2025-01-10T14:20:15.000Z",
      "offset": 15.0,
      "confidence": 0.97
    }
  ],
  "summary": {
    "topics": ["account", "billing", "payment"],
    "sentiment": "neutral",
    "resolution": "resolved"
  },
  "created_at": "2025-01-10T14:25:31.000Z"
}
```

## File Storage Schema

For archival or backup purposes, transcripts can be exported to JSON files:

### Directory Structure

```
transcripts/
├── 2025/
│   ├── 01/
│   │   ├── 10/
│   │   │   ├── CA1234567890abcdef1234567890abcdef.json
│   │   │   ├── CA9876543210fedcba9876543210fedcba.json
│   │   │   └── ...
│   │   └── 11/
│   └── 02/
└── index/
    ├── by_user/
    │   ├── user_507f191e810c19729de860ea.json
    │   └── ...
    └── by_date/
        ├── 2025-01-10.json
        └── ...
```

### File Format: `{call_sid}.json`

```json
{
  "version": "1.0",
  "schema": "https://yourapp.com/schemas/transcript/v1",
  "call": {
    "call_sid": "CA1234567890abcdef1234567890abcdef",
    "user_id": "507f191e810c19729de860ea",
    "started_at": "2025-01-10T14:20:00.000Z",
    "ended_at": "2025-01-10T14:25:30.000Z",
    "duration_sec": 330
  },
  "metadata": {
    "provider": "deepgram",
    "model": "nova-2",
    "language": "en-US",
    "total_utterances": 45,
    "average_confidence": 0.96
  },
  "transcripts": [
    /* Array of transcript objects */
  ],
  "exported_at": "2025-01-10T15:00:00.000Z"
}
```

## Scalability Considerations

### Partitioning Strategy

For high-volume systems (>1M calls/month):

1. **Time-based Sharding**
   - Partition by month: `transcripts_2025_01`, `transcripts_2025_02`
   - Archive old partitions to cold storage
   - Query recent partitions for better performance

2. **Call-based Sharding**
   - Shard by call_sid hash
   - Distribute across multiple MongoDB instances
   - Use MongoDB sharding with `call_sid` as shard key

### Storage Optimization

1. **Compression**
   - Enable MongoDB document compression (Snappy/Zstandard)
   - Compress archived JSON files (gzip)
   - Expected: 70-80% storage reduction

2. **Field Selection**
   - Store only `is_final: true` transcripts
   - Optional: Store `words` array separately
   - Archive interim results after 24 hours

3. **TTL Policies**
   - Keep hot data (0-30 days) in primary storage
   - Move warm data (31-90 days) to secondary storage
   - Archive cold data (90+ days) to S3/GCS

### Query Optimization

1. **Indexes**
   - Compound indexes for common query patterns
   - Sparse indexes for optional fields
   - Text indexes for full-text search

2. **Aggregation Pipelines**
   - Pre-compute aggregations for analytics
   - Cache frequently accessed aggregations
   - Use materialized views for dashboards

3. **Caching**
   - Redis cache for recent transcripts
   - Cache TTL: 5 minutes
   - Cache key: `transcript:{call_sid}`

### Write Performance

Expected throughput:
- **Concurrent calls**: 1,000+
- **Transcripts/second**: 10,000+
- **Write latency**: <10ms

Optimization techniques:
1. Batch inserts (100 documents/batch)
2. Async writes with acknowledgment
3. Write concern: majority
4. Connection pooling (min: 10, max: 100)

## Analytics Schema

### Call Analytics Aggregate

For analytics and reporting:

```json
{
  "_id": "2025-01-10",
  "date": "2025-01-10",
  "metrics": {
    "total_calls": 1250,
    "total_transcripts": 45678,
    "total_words": 523456,
    "avg_call_duration": 287.5,
    "avg_confidence": 0.96,
    "languages": {
      "en-US": 1100,
      "es": 100,
      "fr": 50
    },
    "speakers": {
      "caller": 22839,
      "agent": 22839
    }
  },
  "quality": {
    "low_confidence_count": 234,  // <0.8
    "high_confidence_count": 45444,  // >=0.8
    "avg_words_per_utterance": 11.5
  }
}
```

## Security & Privacy

### PII Handling

1. **Redaction**
   - Automatically detect and redact PII
   - Store redacted version in `text_redacted` field
   - Keep original with encryption

2. **Encryption**
   - Encrypt sensitive fields at rest
   - Use MongoDB field-level encryption
   - Rotate encryption keys quarterly

3. **Access Control**
   - Role-based access to transcripts
   - Audit log for transcript access
   - User consent required for storage

### Compliance

- **GDPR**: Right to erasure support
- **HIPAA**: Encryption and audit logs
- **PCI-DSS**: No payment card data in transcripts
- **Retention**: Configurable per regulations

## Migration Path

From existing schema to new schema:

```python
# Migration script
def migrate_transcript(old_doc):
    return {
        "call_sid": old_doc["call_sid"],
        "user_id": old_doc.get("user_id"),
        "speaker": old_doc.get("speaker", "unknown"),
        "text": old_doc["text"],
        "ts": old_doc["ts"],
        "confidence": old_doc.get("confidence"),
        "is_final": old_doc.get("is_final", True),
        "language": "en-US",
        "metadata": {
            "provider": "deepgram",
            "model": "nova-2"
        },
        "created_at": old_doc["created_at"]
    }
```

## Future Enhancements

1. **Real-time Analytics**
   - Stream transcripts to analytics platform
   - Real-time sentiment analysis
   - Live keyword detection

2. **Machine Learning**
   - Train custom models on transcript data
   - Automatic topic categorization
   - Intent detection

3. **Multi-language Support**
   - Language detection per utterance
   - Mixed-language calls
   - Translation support

4. **Speaker Diarization**
   - Automatic speaker identification
   - Speaker embeddings
   - Voice biometrics
