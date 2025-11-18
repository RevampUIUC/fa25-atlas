# Call Retry Logic - Track 1

## Retry Policy Summary

This document defines the automatic retry behavior for failed Twilio calls.

---

## Retry Policy Table

| Call Status | Expected Retry? | Max Attempts | Final call.status | Notes |
|-------------|----------------|--------------|-------------------|-------|
| `busy` | **Yes** | **3** | `busy` (last non-completed) | Recipient's line is busy - retry likely to succeed later |
| `no-answer` | **Yes** | **3** | `no-answer` (last non-completed) | No one answered - recipient may be available later |
| `failed` | **Yes** | **3** | `failed` (last non-completed) | Technical failure - network issues may be temporary |
| `completed` | **No** | n/a | `completed` | Call successfully connected - no retry needed |
| `in-progress` | **No** | n/a | `in-progress` | Call is currently active - no retry |
| `ringing` | **No** | n/a | `ringing` | Call is currently ringing - no retry |

---

## Retry Behavior Details

### Statuses That Trigger Retries

**1. Busy (`busy`)**
- **Reason:** Recipient's phone line is busy
- **Retry Strategy:** Wait and retry (recipient may hang up)
- **Max Attempts:** 3
- **Backoff:** Exponential (5 min, 15 min, 30 min)

**2. No Answer (`no-answer`)**
- **Reason:** Call rang but no one answered
- **Retry Strategy:** Try at different times
- **Max Attempts:** 3
- **Backoff:** Exponential (5 min, 15 min, 30 min)

**3. Failed (`failed`)**
- **Reason:** Technical failure (network, invalid number, etc.)
- **Retry Strategy:** Retry in case of temporary issues
- **Max Attempts:** 3
- **Backoff:** Exponential (5 min, 15 min, 30 min)

### Statuses That Do NOT Trigger Retries

**1. Completed (`completed`)**
- Call successfully connected
- No retry necessary

**2. In Progress (`in-progress`)**
- Call is currently active
- Should not retry an active call

**3. Ringing (`ringing`)**
- Call is currently ringing
- Wait for final status

---

## Database Schema for Retries

### Call Document Structure

```json
{
  "_id": ObjectId("..."),
  "call_sid": "CA1234567890abcdef1234567890abcdef",
  "status": "busy",
  "attempt_count": 2,
  "max_attempts": 3,
  "should_retry": true,
  "next_retry_at": "2024-11-11T12:30:00Z",
  "attempts": [
    {
      "attempt_number": 1,
      "call_sid": "CA1234567890abcdef1234567890abcdef",
      "status": "busy",
      "timestamp": "2024-11-11T12:00:00Z",
      "reason": "Recipient line busy"
    },
    {
      "attempt_number": 2,
      "call_sid": "CA9876543210fedcba9876543210fedcba",
      "status": "busy",
      "timestamp": "2024-11-11T12:15:00Z",
      "reason": "Recipient line still busy"
    }
  ],
  "created_at": "2024-11-11T12:00:00Z",
  "updated_at": "2024-11-11T12:15:00Z"
}
```

### Key Fields

- **`attempt_count`**: Number of attempts made so far
- **`max_attempts`**: Maximum retry attempts (default: 3)
- **`should_retry`**: Boolean flag indicating if retry is needed
- **`next_retry_at`**: Timestamp for next scheduled retry
- **`attempts[]`**: Array of all attempt records

---

## Retry Logic Flow

```
Call Initiated
    ↓
[Status: initiated]
    ↓
Twilio Dials
    ↓
[Status: ringing or busy/no-answer/failed]
    ↓
    ├─ If busy/no-answer/failed:
    │    ↓
    │  Check attempt_count < max_attempts?
    │    ↓
    │  Yes: Schedule Retry
    │    ├─ Increment attempt_count
    │    ├─ Set next_retry_at (exponential backoff)
    │    ├─ Log attempt in attempts[]
    │    └─ Create new call at next_retry_at
    │    ↓
    │  No: Mark as Final Failure
    │    └─ Set should_retry = false
    │
    └─ If completed:
         └─ Mark as Success (no retry)
```

---

## Exponential Backoff Schedule

| Attempt | Delay | Cumulative Time |
|---------|-------|----------------|
| 1 → 2   | 5 min | 5 min |
| 2 → 3   | 15 min | 20 min |
| 3 → END | n/a | Final |

**Formula:** `delay = 5 * (2 ^ (attempt_number - 1))` minutes

---

## Implementation Notes

### When to Increment `attempt_count`

Increment **ONLY when**:
- Previous attempt resulted in `busy`, `no-answer`, or `failed`
- `attempt_count < max_attempts`
- A new call is initiated (retry)

### When to Set `should_retry = false`

Set to false when:
- Call status is `completed` (success)
- `attempt_count >= max_attempts` (exhausted retries)
- User manually cancels retry

### When to Schedule Next Retry

Schedule retry when:
- Current status is `busy`, `no-answer`, or `failed`
- `attempt_count < max_attempts`
- Calculate `next_retry_at` using exponential backoff

---

## API Endpoints for Retry Management

### Get Call with Retry Info

```http
GET /calls/{call_sid}/debug
```

**Response:**
```json
{
  "call_sid": "CA123...",
  "status": "busy",
  "attempt_count": 2,
  "max_attempts": 3,
  "should_retry": true,
  "next_retry_at": "2024-11-11T12:30:00Z",
  "attempts": [...]
}
```

### Manually Trigger Retry

```http
POST /calls/{call_sid}/retry
```

**Response:**
```json
{
  "new_call_sid": "CA987...",
  "attempt_number": 3,
  "scheduled_at": "2024-11-11T12:30:00Z"
}
```

### Cancel Scheduled Retry

```http
DELETE /calls/{call_sid}/retry
```

**Response:**
```json
{
  "call_sid": "CA123...",
  "should_retry": false,
  "message": "Retry cancelled"
}
```

---

## Testing Retry Logic

### Test Scenario 1: Busy → Busy → Completed

1. Make call → Status: `busy`
   - `attempt_count` = 1
   - `should_retry` = true
   - `next_retry_at` = +5 min

2. Retry → Status: `busy`
   - `attempt_count` = 2
   - `should_retry` = true
   - `next_retry_at` = +15 min

3. Retry → Status: `completed`
   - `attempt_count` = 3
   - `should_retry` = false
   - Final status: `completed`

### Test Scenario 2: No Answer → No Answer → No Answer (Max Reached)

1. Make call → Status: `no-answer`
   - `attempt_count` = 1

2. Retry → Status: `no-answer`
   - `attempt_count` = 2

3. Retry → Status: `no-answer`
   - `attempt_count` = 3
   - `should_retry` = false
   - Final status: `no-answer`

---

## Monitoring & Alerts

### Metrics to Track

- **Retry Success Rate**: % of retries that result in `completed`
- **Average Attempts per Call**: Mean `attempt_count` for all calls
- **Max Attempts Reached**: Count of calls hitting retry limit
- **Status Distribution**: Breakdown of final call statuses

### Alert Thresholds

- **High Failure Rate**: > 30% of calls reaching max attempts
- **Low Retry Success**: < 20% of retries succeeding
- **Unusual Patterns**: Spike in `busy` or `no-answer` statuses

---

## Future Enhancements

1. **Adaptive Backoff**: Adjust delays based on time of day
2. **Smart Scheduling**: Avoid retrying during known busy hours
3. **Per-User Retry Limits**: Different max_attempts for VIP users
4. **Status-Specific Backoff**: Different delays for `busy` vs `no-answer`
5. **Manual Override**: Allow users to force immediate retry

---

**Last Updated:** November 10, 2024  
**Version:** 1.0  
**Owner:** Track 1 Team