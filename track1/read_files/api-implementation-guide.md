# API Implementation Guide

## Routes to Implement

### 1. GET /users/:userId/calls/:callId

**Purpose:** Retrieve detailed information about a specific call, including all retry attempts.

**Implementation:**

```javascript
// routes/calls.js or routes/users.js

const express = require('express');
const router = express.Router();
const Call = require('../models/Call'); // Your Mongoose model

/**
 * GET /users/:userId/calls/:callId
 * Get detailed call information including all attempts
 */
router.get('/users/:userId/calls/:callId', async (req, res) => {
  try {
    const { userId, callId } = req.params;
    
    // Find the call
    const call = await Call.findOne({
      _id: callId,
      user_id: userId
    });
    
    if (!call) {
      return res.status(404).json({
        error: 'Call not found',
        message: `No call found with id ${callId} for user ${userId}`
      });
    }
    
    // Return call data with all attempts
    res.json({
      call_id: call._id,
      user_id: call.user_id,
      to: call.to,
      from: call.from,
      status: call.status,
      attempt_count: call.attempt_count,
      max_attempts: call.max_attempts || 3,
      should_retry: call.should_retry,
      next_retry_at: call.next_retry_at,
      attempts: call.attempts,
      created_at: call.created_at,
      updated_at: call.updated_at
    });
    
  } catch (error) {
    console.error('Error fetching call:', error);
    res.status(500).json({
      error: 'Internal server error',
      message: error.message
    });
  }
});

module.exports = router;
```

---

### 2. GET /users/:userId/calls

**Purpose:** List all calls for a user (useful for debugging and monitoring).

**Implementation:**

```javascript
/**
 * GET /users/:userId/calls
 * Get all calls for a specific user
 */
router.get('/users/:userId/calls', async (req, res) => {
  try {
    const { userId } = req.params;
    const { status, limit = 50, offset = 0 } = req.query;
    
    // Build query
    const query = { user_id: userId };
    if (status) {
      query.status = status;
    }
    
    // Get calls with pagination
    const calls = await Call.find(query)
      .sort({ created_at: -1 })
      .limit(parseInt(limit))
      .skip(parseInt(offset));
    
    const total = await Call.countDocuments(query);
    
    res.json({
      user_id: userId,
      total,
      limit: parseInt(limit),
      offset: parseInt(offset),
      calls: calls.map(call => ({
        call_id: call._id,
        to: call.to,
        status: call.status,
        attempt_count: call.attempt_count,
        should_retry: call.should_retry,
        created_at: call.created_at
      }))
    });
    
  } catch (error) {
    console.error('Error fetching calls:', error);
    res.status(500).json({
      error: 'Internal server error',
      message: error.message
    });
  }
});
```

---

### 3. POST /calls/outbound (Enhanced with Retry Support)

**Purpose:** Create a new outbound call with retry tracking.

**Implementation:**

```javascript
/**
 * POST /calls/outbound
 * Create a new outbound call
 */
router.post('/calls/outbound', async (req, res) => {
  try {
    const { to, from, user_id } = req.body;
    
    // Validate input
    if (!to || !from || !user_id) {
      return res.status(400).json({
        error: 'Missing required fields',
        required: ['to', 'from', 'user_id']
      });
    }
    
    // Make Twilio call
    const twilioCall = await twilioClient.calls.create({
      to,
      from,
      url: `${process.env.BASE_URL}/twilio/voice`,
      statusCallback: `${process.env.BASE_URL}/twilio/status`,
      statusCallbackEvent: ['completed', 'busy', 'no-answer', 'failed']
    });
    
    // Create call record with first attempt
    const call = new Call({
      user_id,
      to,
      from,
      twilio_sid: twilioCall.sid,
      status: 'initiated',
      attempt_count: 1,
      max_attempts: 3,
      should_retry: false,
      attempts: [{
        attempt_number: 1,
        twilio_sid: twilioCall.sid,
        status: 'initiated',
        timestamp: new Date()
      }]
    });
    
    await call.save();
    
    res.json({
      call_id: call._id,
      user_id: call.user_id,
      twilio_sid: twilioCall.sid,
      status: call.status,
      attempt_count: call.attempt_count,
      to: call.to,
      from: call.from
    });
    
  } catch (error) {
    console.error('Error creating outbound call:', error);
    res.status(500).json({
      error: 'Failed to create call',
      message: error.message
    });
  }
});
```

---

### 4. POST /twilio/status (Enhanced with Retry Logic)

**Purpose:** Handle Twilio status callbacks and trigger retries when needed.

**Implementation:**

```javascript
/**
 * POST /twilio/status
 * Twilio status callback webhook
 */
router.post('/twilio/status', async (req, res) => {
  try {
    const { CallSid, CallStatus } = req.body;
    
    // Acknowledge receipt immediately
    res.json({ status: 'ok' });
    
    // Process async to not block Twilio
    processStatusUpdate(CallSid, CallStatus).catch(err => {
      console.error('Error processing status update:', err);
    });
    
  } catch (error) {
    console.error('Error in status callback:', error);
    res.status(500).json({ status: 'error', message: error.message });
  }
});

/**
 * Process status update and handle retry logic
 */
async function processStatusUpdate(twilioSid, status) {
  // Find the call by the attempt's twilio_sid
  const call = await Call.findOne({
    'attempts.twilio_sid': twilioSid
  });
  
  if (!call) {
    console.error(`Call not found for Twilio SID: ${twilioSid}`);
    return;
  }
  
  // Update the current attempt status
  const currentAttempt = call.attempts.find(a => a.twilio_sid === twilioSid);
  if (currentAttempt) {
    currentAttempt.status = status;
  }
  
  // Update overall call status
  call.status = status;
  call.updated_at = new Date();
  
  // Determine if retry is needed
  const shouldRetry = ['busy', 'no-answer', 'failed'].includes(status);
  const canRetry = call.attempt_count < call.max_attempts;
  
  if (shouldRetry && canRetry) {
    // Schedule retry
    call.should_retry = true;
    
    // Calculate next retry time with exponential backoff
    const retryDelays = [2 * 60 * 1000, 5 * 60 * 1000, 10 * 60 * 1000]; // 2min, 5min, 10min
    const delayIndex = call.attempt_count - 1;
    const delay = retryDelays[delayIndex] || retryDelays[retryDelays.length - 1];
    
    call.next_retry_at = new Date(Date.now() + delay);
    
    console.log(`Scheduling retry for call ${call._id}, attempt ${call.attempt_count + 1}`);
  } else {
    call.should_retry = false;
    call.next_retry_at = null;
    
    if (status === 'completed') {
      console.log(`Call ${call._id} completed successfully on attempt ${call.attempt_count}`);
    } else if (!canRetry) {
      console.log(`Call ${call._id} reached max attempts (${call.max_attempts})`);
    }
  }
  
  await call.save();
  
  // If retry scheduled, trigger retry job (or let cron pick it up)
  if (call.should_retry) {
    // Option 1: Use setTimeout for immediate scheduling
    // setTimeout(() => retryCall(call._id), delay);
    
    // Option 2: Let your retry job/cron handle it
    // (no action needed here)
  }
}
```

---

### 5. Retry Job Implementation

**Purpose:** Background job to process scheduled retries.

**Implementation:**

```javascript
// jobs/retryJob.js

const Call = require('../models/Call');
const twilioClient = require('../config/twilio');

/**
 * Retry job - runs every minute to process due retries
 */
async function processRetries() {
  try {
    // Find calls due for retry
    const callsToRetry = await Call.find({
      should_retry: true,
      next_retry_at: { $lte: new Date() },
      attempt_count: { $lt: 3 }
    });
    
    console.log(`Found ${callsToRetry.length} calls to retry`);
    
    for (const call of callsToRetry) {
      await retryCall(call);
    }
    
  } catch (error) {
    console.error('Error in retry job:', error);
  }
}

/**
 * Retry a specific call
 */
async function retryCall(call) {
  try {
    console.log(`Retrying call ${call._id}, attempt ${call.attempt_count + 1}`);
    
    // Make new Twilio call
    const twilioCall = await twilioClient.calls.create({
      to: call.to,
      from: call.from,
      url: `${process.env.BASE_URL}/twilio/voice`,
      statusCallback: `${process.env.BASE_URL}/twilio/status`,
      statusCallbackEvent: ['completed', 'busy', 'no-answer', 'failed']
    });
    
    // Update call record
    call.attempt_count += 1;
    call.should_retry = false; // Will be set again if this attempt fails
    call.next_retry_at = null;
    
    // Add new attempt
    call.attempts.push({
      attempt_number: call.attempt_count,
      twilio_sid: twilioCall.sid,
      status: 'initiated',
      timestamp: new Date()
    });
    
    await call.save();
    
    console.log(`Successfully initiated retry for call ${call._id}`);
    
  } catch (error) {
    console.error(`Error retrying call ${call._id}:`, error);
    
    // Mark as failed
    call.status = 'failed';
    call.should_retry = false;
    call.attempts.push({
      attempt_number: call.attempt_count + 1,
      status: 'failed',
      timestamp: new Date(),
      error_message: error.message
    });
    
    await call.save();
  }
}

// Export for use in cron or manual trigger
module.exports = { processRetries, retryCall };

// If running as standalone script
if (require.main === module) {
  processRetries().then(() => {
    console.log('Retry job completed');
    process.exit(0);
  }).catch(err => {
    console.error('Retry job failed:', err);
    process.exit(1);
  });
}
```

---

## Integration Steps

1. **Add routes to your Express app:**

```javascript
// app.js or server.js
const callsRouter = require('./routes/calls');
app.use('/', callsRouter);
```

2. **Set up retry job with cron:**

```javascript
// Using node-cron
const cron = require('node-cron');
const { processRetries } = require('./jobs/retryJob');

// Run every minute
cron.schedule('* * * * *', async () => {
  console.log('Running retry job...');
  await processRetries();
});
```

3. **Update your Call model schema:**

Ensure your Mongoose schema includes all required fields for retry tracking.

4. **Test with Postman:**

Import the `Track1-Week2.postman_collection.json` and run the test suite.