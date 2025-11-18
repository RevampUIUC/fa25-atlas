#!/usr/bin/env node

/**
 * Sample MongoDB Export Script
 * Exports call attempts for a specific day to JSON
 * 
 * Usage:
 *   node sample_mongo_export.js [date]
 *   node sample_mongo_export.js 2025-11-11
 *   node sample_mongo_export.js  (defaults to today)
 */

const { MongoClient } = require('mongodb');
const fs = require('fs');
const path = require('path');

// Configuration
const MONGO_URI = process.env.MONGODB_URI || 'mongodb://localhost:27017';
const DB_NAME = process.env.DB_NAME || 'track1_calls';
const COLLECTION_NAME = 'calls';

// Parse command line arguments
const targetDate = process.argv[2] || new Date().toISOString().split('T')[0];

async function exportDailyAttempts() {
  const client = new MongoClient(MONGO_URI);
  
  try {
    console.log(`Connecting to MongoDB...`);
    await client.connect();
    console.log(`Connected successfully`);
    
    const db = client.db(DB_NAME);
    const collection = db.collection(COLLECTION_NAME);
    
    // Parse target date
    const dateObj = new Date(targetDate);
    const startOfDay = new Date(dateObj.setHours(0, 0, 0, 0));
    const endOfDay = new Date(dateObj.setHours(23, 59, 59, 999));
    
    console.log(`Exporting attempts for date: ${targetDate}`);
    console.log(`Range: ${startOfDay.toISOString()} to ${endOfDay.toISOString()}`);
    
    // Query calls for the day
    const calls = await collection.find({
      created_at: {
        $gte: startOfDay,
        $lte: endOfDay
      }
    }).toArray();
    
    console.log(`Found ${calls.length} calls`);
    
    // Calculate statistics
    const stats = {
      total_calls: calls.length,
      total_attempts: calls.reduce((sum, call) => sum + call.attempt_count, 0),
      by_status: {},
      by_attempt_count: {},
      max_retries_reached: 0,
      completed_first_try: 0
    };
    
    calls.forEach(call => {
      // Status breakdown
      stats.by_status[call.status] = (stats.by_status[call.status] || 0) + 1;
      
      // Attempt count breakdown
      stats.by_attempt_count[call.attempt_count] = 
        (stats.by_attempt_count[call.attempt_count] || 0) + 1;
      
      // Max retries
      if (call.attempt_count >= 3 && call.status !== 'completed') {
        stats.max_retries_reached++;
      }
      
      // First try success
      if (call.attempt_count === 1 && call.status === 'completed') {
        stats.completed_first_try++;
      }
    });
    
    // Calculate success rate
    const completedCalls = stats.by_status.completed || 0;
    stats.success_rate = calls.length > 0 
      ? ((completedCalls / calls.length) * 100).toFixed(2) + '%'
      : '0%';
    
    // Prepare export data
    const exportData = {
      export_date: new Date().toISOString(),
      target_date: targetDate,
      date_range: {
        start: startOfDay.toISOString(),
        end: endOfDay.toISOString()
      },
      statistics: stats,
      calls: calls.map(call => ({
        id: call._id.toString(),
        user_id: call.user_id,
        to: call.to,
        from: call.from,
        status: call.status,
        attempt_count: call.attempt_count,
        should_retry: call.should_retry,
        created_at: call.created_at,
        attempts: call.attempts.map(attempt => ({
          attempt_number: attempt.attempt_number,
          status: attempt.status,
          timestamp: attempt.timestamp,
          twilio_sid: attempt.twilio_sid,
          error_message: attempt.error_message
        }))
      }))
    };
    
    // Create output directory if it doesn't exist
    const outputDir = path.join(__dirname, '..', 'exports');
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }
    
    // Write to file
    const filename = `call-attempts-${targetDate}.json`;
    const filepath = path.join(outputDir, filename);
    fs.writeFileSync(filepath, JSON.stringify(exportData, null, 2));
    
    console.log(`\n=== Export Summary ===`);
    console.log(`Total calls: ${stats.total_calls}`);
    console.log(`Total attempts: ${stats.total_attempts}`);
    console.log(`Success rate: ${stats.success_rate}`);
    console.log(`Completed first try: ${stats.completed_first_try}`);
    console.log(`Max retries reached: ${stats.max_retries_reached}`);
    console.log(`\nStatus breakdown:`);
    Object.entries(stats.by_status).forEach(([status, count]) => {
      console.log(`  ${status}: ${count}`);
    });
    console.log(`\nAttempt count breakdown:`);
    Object.entries(stats.by_attempt_count).forEach(([attempts, count]) => {
      console.log(`  ${attempts} attempts: ${count} calls`);
    });
    console.log(`\nExported to: ${filepath}`);
    
  } catch (error) {
    console.error('Error exporting data:', error);
    process.exit(1);
  } finally {
    await client.close();
    console.log('Connection closed');
  }
}

// Run the export
exportDailyAttempts();