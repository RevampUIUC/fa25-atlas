// models/Call.js

const mongoose = require('mongoose');

/**
 * Schema for individual call attempts
 */
const attemptSchema = new mongoose.Schema({
  attempt_number: {
    type: Number,
    required: true
  },
  twilio_sid: {
    type: String,
    required: true
  },
  status: {
    type: String,
    required: true,
    enum: ['initiated', 'ringing', 'in-progress', 'completed', 'busy', 'no-answer', 'failed', 'canceled']
  },
  timestamp: {
    type: Date,
    required: true,
    default: Date.now
  },
  error_message: {
    type: String,
    default: null
  },
  duration: {
    type: Number, // Duration in seconds
    default: null
  }
}, { _id: false });

/**
 * Main Call schema with retry support
 */
const callSchema = new mongoose.Schema({
  user_id: {
    type: String,
    required: true,
    index: true
  },
  to: {
    type: String,
    required: true
  },
  from: {
    type: String,
    required: true
  },
  twilio_sid: {
    type: String,
    required: true,
    unique: true,
    index: true
  },
  status: {
    type: String,
    required: true,
    default: 'initiated',
    enum: ['initiated', 'ringing', 'in-progress', 'completed', 'busy', 'no-answer', 'failed', 'canceled']
  },
  
  // Retry tracking fields
  attempt_count: {
    type: Number,
    required: true,
    default: 1,
    min: 1
  },
  max_attempts: {
    type: Number,
    required: true,
    default: 3,
    min: 1
  },
  should_retry: {
    type: Boolean,
    required: true,
    default: false
  },
  next_retry_at: {
    type: Date,
    default: null
  },
  
  // Array of all attempts
  attempts: {
    type: [attemptSchema],
    required: true,
    default: []
  },
  
  // Metadata
  recording_url: {
    type: String,
    default: null
  },
  recording_duration: {
    type: Number,
    default: null
  },
  
  // Timestamps
  created_at: {
    type: Date,
    required: true,
    default: Date.now
  },
  updated_at: {
    type: Date,
    required: true,
    default: Date.now
  }
});

// Indexes for efficient queries
callSchema.index({ user_id: 1, created_at: -1 });
callSchema.index({ status: 1, created_at: -1 });
callSchema.index({ should_retry: 1, next_retry_at: 1, attempt_count: 1 });
callSchema.index({ 'attempts.twilio_sid': 1 });

// Update the updated_at timestamp before saving
callSchema.pre('save', function(next) {
  this.updated_at = new Date();
  next();
});

/**
 * Instance method: Check if call can be retried
 */
callSchema.methods.canRetry = function() {
  const retryableStatuses = ['busy', 'no-answer', 'failed'];
  return retryableStatuses.includes(this.status) && 
         this.attempt_count < this.max_attempts;
};

/**
 * Instance method: Schedule next retry
 */
callSchema.methods.scheduleRetry = function(delayMinutes = null) {
  if (!this.canRetry()) {
    return false;
  }
  
  // Default exponential backoff: 2min, 5min, 10min
  const delays = [2, 5, 10];
  const delayIndex = this.attempt_count - 1;
  const delay = delayMinutes || delays[delayIndex] || delays[delays.length - 1];
  
  this.should_retry = true;
  this.next_retry_at = new Date(Date.now() + delay * 60 * 1000);
  
  return true;
};

/**
 * Instance method: Add a new attempt
 */
callSchema.methods.addAttempt = function(twilioSid, status, errorMessage = null) {
  this.attempt_count += 1;
  this.attempts.push({
    attempt_number: this.attempt_count,
    twilio_sid: twilioSid,
    status: status,
    timestamp: new Date(),
    error_message: errorMessage
  });
  this.status = status;
};

/**
 * Static method: Find calls needing retry
 */
callSchema.statics.findRetryDue = function() {
  return this.find({
    should_retry: true,
    next_retry_at: { $lte: new Date() },
    attempt_count: { $lt: this.schema.path('max_attempts').defaultValue || 3 }
  });
};

/**
 * Static method: Get retry statistics
 */
callSchema.statics.getRetryStats = async function(startDate, endDate) {
  const pipeline = [
    {
      $match: {
        created_at: {
          $gte: startDate,
          $lte: endDate
        }
      }
    },
    {
      $group: {
        _id: null,
        total_calls: { $sum: 1 },
        total_attempts: { $sum: '$attempt_count' },
        completed_first_try: {
          $sum: {
            $cond: [
              { $and: [
                { $eq: ['$status', 'completed'] },
                { $eq: ['$attempt_count', 1] }
              ]},
              1,
              0
            ]
          }
        },
        max_retries_reached: {
          $sum: {
            $cond: [
              { $and: [
                { $gte: ['$attempt_count', 3] },
                { $ne: ['$status', 'completed'] }
              ]},
              1,
              0
            ]
          }
        },
        completed_total: {
          $sum: {
            $cond: [{ $eq: ['$status', 'completed'] }, 1, 0]
          }
        }
      }
    }
  ];
  
  const result = await this.aggregate(pipeline);
  return result[0] || {
    total_calls: 0,
    total_attempts: 0,
    completed_first_try: 0,
    max_retries_reached: 0,
    completed_total: 0
  };
};

/**
 * Virtual: Success on first attempt
 */
callSchema.virtual('first_attempt_success').get(function() {
  return this.status === 'completed' && this.attempt_count === 1;
});

/**
 * Virtual: Reached max attempts
 */
callSchema.virtual('max_attempts_reached').get(function() {
  return this.attempt_count >= this.max_attempts;
});

/**
 * Convert to JSON with virtuals
 */
callSchema.set('toJSON', { virtuals: true });
callSchema.set('toObject', { virtuals: true });

// Create and export the model
const Call = mongoose.model('Call', callSchema);

module.exports = Call;