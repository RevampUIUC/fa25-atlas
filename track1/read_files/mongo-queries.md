# MongoDB Queries for Call Retry Monitoring

## Quick Reference: 5 Essential Queries

### 1. Show All Attempts for a Specific Call

```javascript
db.calls.findOne(
  { _id: ObjectId("YOUR_CALL_ID_HERE") },
  { 
    attempts: 1, 
    attempt_count: 1, 
    status: 1, 
    should_retry: 1,
    next_retry_at: 1 
  }
)
```

**What it shows:** Complete attempt history, current count, and retry status for a single call.

---

### 2. Show Calls Needing Retry Now

```javascript
db.calls.find({
  should_retry: true,
  next_retry_at: { $lte: new Date() },
  attempt_count: { $lt: 3 }
}).pretty()
```

**What it shows:** All calls that are due for retry right now (past their `next_retry_at` time).

**Alternative (with projection):**
```javascript
db.calls.find(
  {
    should_retry: true,
    next_retry_at: { $lte: new Date() },
    attempt_count: { $lt: 3 }
  },
  {
    twilio_sid: 1,
    to: 1,
    status: 1,
    attempt_count: 1,
    next_retry_at: 1
  }
).pretty()
```

---

### 3. Count Calls by Final Status Today

```javascript
db.calls.aggregate([
  {
    $match: {
      created_at: {
        $gte: new Date(new Date().setHours(0, 0, 0, 0)),
        $lt: new Date(new Date().setHours(23, 59, 59, 999))
      }
    }
  },
  {
    $group: {
      _id: "$status",
      count: { $sum: 1 }
    }
  },
  {
    $sort: { count: -1 }
  }
])
```

**What it shows:** Summary of how many calls ended in each status (completed, busy, no-answer, failed) for today.

**Example output:**
```javascript
[
  { _id: "completed", count: 45 },
  { _id: "busy", count: 12 },
  { _id: "no-answer", count: 8 },
  { _id: "failed", count: 3 }
]
```

---

### 4. Show All Attempts with Timestamps (Detailed View)

```javascript
db.calls.find(
  { attempt_count: { $gt: 1 } },
  {
    twilio_sid: 1,
    to: 1,
    status: 1,
    attempt_count: 1,
    "attempts.attempt_number": 1,
    "attempts.status": 1,
    "attempts.timestamp": 1,
    created_at: 1
  }
).sort({ created_at: -1 }).limit(10)
```

**What it shows:** Recent calls with multiple attempts, showing the progression of each retry.

---

### 5. Find Calls That Maxed Out Retries

```javascript
db.calls.find({
  attempt_count: { $gte: 3 },
  status: { $ne: "completed" }
}).pretty()
```

**What it shows:** Calls that hit the maximum retry limit without completing successfully.

**With count:**
```javascript
db.calls.countDocuments({
  attempt_count: { $gte: 3 },
  status: { $ne: "completed" }
})
```

---

## Bonus Queries

### Find Calls for a Specific User

```javascript
db.calls.find(
  { user_id: "test_user_123" }
).sort({ created_at: -1 })
```

### Show Retry Schedule for Next Hour

```javascript
db.calls.find(
  {
    should_retry: true,
    next_retry_at: {
      $gte: new Date(),
      $lte: new Date(Date.now() + 60 * 60 * 1000)
    }
  },
  {
    to: 1,
    attempt_count: 1,
    next_retry_at: 1,
    status: 1
  }
).sort({ next_retry_at: 1 })
```

### Average Attempts Per Call

```javascript
db.calls.aggregate([
  {
    $group: {
      _id: null,
      avgAttempts: { $avg: "$attempt_count" },
      totalCalls: { $sum: 1 }
    }
  }
])
```

### Success Rate by Attempt Number

```javascript
db.calls.aggregate([
  { $unwind: "$attempts" },
  {
    $group: {
      _id: {
        attempt: "$attempts.attempt_number",
        status: "$attempts.status"
      },
      count: { $sum: 1 }
    }
  },
  { $sort: { "_id.attempt": 1, "count": -1 } }
])
```

---

## Tips for Using These Queries

1. **Replace placeholders**: Change `YOUR_CALL_ID_HERE` and `test_user_123` with actual values
2. **Date ranges**: Adjust the date filters in queries to match your timezone
3. **Pretty print**: Add `.pretty()` to any query for formatted output
4. **Explain plans**: Add `.explain()` to see query performance
5. **Indexes**: Consider adding indexes on:
   - `{ should_retry: 1, next_retry_at: 1, attempt_count: 1 }`
   - `{ user_id: 1, created_at: -1 }`
   - `{ status: 1, created_at: -1 }`

## Creating Useful Indexes

```javascript
// Index for retry job queries
db.calls.createIndex({ 
  should_retry: 1, 
  next_retry_at: 1, 
  attempt_count: 1 
})

// Index for user queries
db.calls.createIndex({ 
  user_id: 1, 
  created_at: -1 
})

// Index for status reporting
db.calls.createIndex({ 
  status: 1, 
  created_at: -1 
})
```