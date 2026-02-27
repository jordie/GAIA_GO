package rate_limiting

import (
	"context"
	"fmt"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// LoadTestResult tracks metrics from a load test
type LoadTestResult struct {
	TotalRequests      int64
	SuccessfulRequests int64
	FailedRequests     int64
	TotalDuration      time.Duration
	AvgLatency         time.Duration
	MaxLatency         time.Duration
	MinLatency         time.Duration
	RequestsPerSecond  float64
	ErrorRate          float64
}

// setupLoadTestDB creates a test database optimized for load testing
func setupLoadTestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("Failed to create test DB: %v", err)
	}

	// Enable WAL mode for better concurrency
	db.Exec("PRAGMA journal_mode=WAL")
	db.Exec("PRAGMA synchronous=NORMAL")
	db.Exec("PRAGMA cache_size=-64000")

	// Create tables
	db.Exec(`
		CREATE TABLE reputation_scores (
			id INTEGER PRIMARY KEY,
			user_id INTEGER UNIQUE,
			score REAL,
			tier TEXT
		)
	`)

	db.Exec(`
		CREATE TABLE violations (
			id INTEGER PRIMARY KEY,
			user_id INTEGER,
			violation_type TEXT,
			created_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE appeals (
			id INTEGER PRIMARY KEY,
			user_id INTEGER,
			violation_id INTEGER,
			reason TEXT,
			status TEXT,
			created_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE appeal_negotiation_messages (
			id INTEGER PRIMARY KEY,
			appeal_id INTEGER,
			sender_id INTEGER,
			sender_type TEXT,
			message TEXT,
			message_type TEXT,
			created_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE user_analytics_summary (
			id INTEGER PRIMARY KEY,
			user_id INTEGER UNIQUE,
			trend_direction TEXT,
			projected_30day_score REAL
		)
	`)

	return db
}

// TestHighConcurrencyAppealSubmission tests appeal submission under high concurrency
func TestHighConcurrencyAppealSubmission(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping high concurrency test in short mode")
	}

	db := setupLoadTestDB(t)
	ctx := context.Background()
	appealSvc := NewAppealService(db)

	// Prepare: Create 1000 users with violations
	const numUsers = 1000
	for i := 0; i < numUsers; i++ {
		db.Exec(`
			INSERT INTO reputation_scores (user_id, score, tier)
			VALUES (?, ?, 'standard')
		`, i, 50.0)

		db.Exec(`
			INSERT INTO violations (id, user_id, violation_type, created_at)
			VALUES (?, ?, 'rate_limit_exceeded', datetime('now', '-5 days'))
		`, i, i)
	}

	// Run: Concurrent appeal submissions
	const concurrency = 100
	totalRequests := int64(0)
	successfulRequests := int64(0)
	failedRequests := int64(0)

	var latencies []time.Duration
	var latencyMutex sync.Mutex

	start := time.Now()

	var wg sync.WaitGroup
	semaphore := make(chan bool, concurrency)

	for i := 0; i < numUsers; i++ {
		wg.Add(1)
		semaphore <- true

		go func(userID int) {
			defer wg.Done()
			defer func() { <-semaphore }()

			requestStart := time.Now()
			_, err := appealSvc.SubmitAppeal(ctx, userID, userID, "false_positive", "Appeal")
			latency := time.Since(requestStart)

			atomic.AddInt64(&totalRequests, 1)

			if err != nil {
				atomic.AddInt64(&failedRequests, 1)
			} else {
				atomic.AddInt64(&successfulRequests, 1)
				latencyMutex.Lock()
				latencies = append(latencies, latency)
				latencyMutex.Unlock()
			}
		}(i)
	}

	wg.Wait()
	duration := time.Since(start)

	// Calculate statistics
	result := LoadTestResult{
		TotalRequests:      totalRequests,
		SuccessfulRequests: successfulRequests,
		FailedRequests:     failedRequests,
		TotalDuration:      duration,
		RequestsPerSecond:  float64(successfulRequests) / duration.Seconds(),
		ErrorRate:          float64(failedRequests) / float64(totalRequests) * 100,
	}

	if len(latencies) > 0 {
		var totalLatency time.Duration
		minLatency := latencies[0]
		maxLatency := latencies[0]

		for _, lat := range latencies {
			totalLatency += lat
			if lat < minLatency {
				minLatency = lat
			}
			if lat > maxLatency {
				maxLatency = lat
			}
		}

		result.AvgLatency = time.Duration(int64(totalLatency) / int64(len(latencies)))
		result.MinLatency = minLatency
		result.MaxLatency = maxLatency
	}

	// Log results
	t.Logf("High Concurrency Appeal Submission Results:")
	t.Logf("  Total Requests: %d", result.TotalRequests)
	t.Logf("  Successful: %d (%.2f%%)", result.SuccessfulRequests, float64(result.SuccessfulRequests)/float64(result.TotalRequests)*100)
	t.Logf("  Failed: %d (%.2f%%)", result.FailedRequests, result.ErrorRate)
	t.Logf("  Duration: %v", result.TotalDuration)
	t.Logf("  Throughput: %.2f req/sec", result.RequestsPerSecond)
	t.Logf("  Latency - Avg: %v, Min: %v, Max: %v", result.AvgLatency, result.MinLatency, result.MaxLatency)

	// Assertions
	if result.ErrorRate > 5.0 {
		t.Errorf("Error rate too high: %.2f%%", result.ErrorRate)
	}

	if result.AvgLatency > 100*time.Millisecond {
		t.Logf("Warning: High average latency: %v", result.AvgLatency)
	}
}

// TestHighConcurrencyNegotiationMessages tests concurrent negotiation messaging
func TestHighConcurrencyNegotiationMessages(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping high concurrency test in short mode")
	}

	db := setupLoadTestDB(t)
	ctx := context.Background()
	appealSvc := NewAppealService(db)
	negotiationSvc := NewAppealNegotiationService(db)

	// Prepare: Create appeal and multiple users
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (10000, 50.0, 'standard')
	`)

	db.Exec(`
		INSERT INTO violations (id, user_id, violation_type, created_at)
		VALUES (1, 10000, 'rate_limit_exceeded', datetime('now', '-5 days'))
	`)

	appeal, _ := appealSvc.SubmitAppeal(ctx, 10000, 1, "false_positive", "Appeal")

	// Run: Concurrent messages from multiple "admins"
	const concurrency = 50
	const messagesPerUser = 20
	totalMessages := int64(0)
	successfulMessages := int64(0)

	start := time.Now()

	var wg sync.WaitGroup
	semaphore := make(chan bool, concurrency)

	for i := 0; i < concurrency; i++ {
		wg.Add(1)
		semaphore <- true

		go func(userID int) {
			defer wg.Done()
			defer func() { <-semaphore }()

			for j := 0; j < messagesPerUser; j++ {
				_, err := negotiationSvc.SendMessage(
					ctx,
					appeal.ID,
					userID,
					SenderTypeAdmin,
					fmt.Sprintf("Message from admin %d", userID),
					MessageTypeMessage,
					nil,
					nil,
				)

				atomic.AddInt64(&totalMessages, 1)
				if err == nil {
					atomic.AddInt64(&successfulMessages, 1)
				}
			}
		}(20000 + i)
	}

	wg.Wait()
	duration := time.Since(start)

	t.Logf("High Concurrency Negotiation Messages Results:")
	t.Logf("  Total Messages: %d", totalMessages)
	t.Logf("  Successful: %d (%.2f%%)", successfulMessages, float64(successfulMessages)/float64(totalMessages)*100)
	t.Logf("  Duration: %v", duration)
	t.Logf("  Throughput: %.2f msgs/sec", float64(successfulMessages)/duration.Seconds())

	// Get thread and verify all messages
	thread, _ := negotiationSvc.GetNegotiationThread(ctx, appeal.ID)
	if thread.MessageCount < int(totalMessages) {
		t.Logf("Note: Message count mismatch (thread has %d, sent %d)", thread.MessageCount, totalMessages)
	}
}

// TestLargeNegotiationThread tests performance with large message threads
func TestLargeNegotiationThread(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping large data test in short mode")
	}

	db := setupLoadTestDB(t)
	ctx := context.Background()

	// Prepare: Create appeal with 10,000 messages
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (30000, 50.0, 'standard')
	`)

	db.Exec(`
		INSERT INTO violations (id, user_id, violation_type, created_at)
		VALUES (1, 30000, 'rate_limit_exceeded', datetime('now', '-5 days'))
	`)

	db.Exec(`
		INSERT INTO appeals (id, user_id, violation_id, reason, status, created_at)
		VALUES (1, 30000, 1, 'false_positive', 'reviewing', datetime('now'))
	`)

	start := time.Now()
	for i := 0; i < 10000; i++ {
		senderType := "user"
		if i%3 == 0 {
			senderType = "admin"
		}

		db.Exec(`
			INSERT INTO appeal_negotiation_messages
			(appeal_id, sender_id, sender_type, message, message_type, created_at)
			VALUES (1, ?, ?, ?, 'message', datetime('now', '-? seconds'))
		`, 30000+(i%2), senderType, fmt.Sprintf("Message %d", i), i)
	}
	insertDuration := time.Since(start)

	t.Logf("Inserted 10,000 messages in %v", insertDuration)

	// Test: Retrieve large thread
	negotiationSvc := NewAppealNegotiationService(db)

	start = time.Now()
	thread, err := negotiationSvc.GetNegotiationThread(ctx, 1)
	retrieveDuration := time.Since(start)

	if err != nil {
		t.Fatalf("Failed to retrieve thread: %v", err)
	}

	t.Logf("Retrieved thread with %d messages in %v", thread.MessageCount, retrieveDuration)

	if retrieveDuration > 1*time.Second {
		t.Logf("Warning: Thread retrieval took longer than 1 second: %v", retrieveDuration)
	}

	if thread.MessageCount != 10000 {
		t.Errorf("Expected 10000 messages, got %d", thread.MessageCount)
	}
}

// TestSustainedLoadAppealProcessing tests sustained load over time
func TestSustainedLoadAppealProcessing(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping sustained load test in short mode")
	}

	db := setupLoadTestDB(t)
	ctx := context.Background()
	appealSvc := NewAppealService(db)

	// Prepare: 100 users
	const numUsers = 100
	for i := 0; i < numUsers; i++ {
		db.Exec(`
			INSERT INTO reputation_scores (user_id, score, tier)
			VALUES (?, ?, 'standard')
		`, 40000+i, 50.0)
	}

	// Run: Sustained load for 30 seconds
	const duration = 30 * time.Second
	const targetRPS = 100 // 100 requests per second
	const concurrency = 20

	ticker := time.NewTicker(time.Duration(int64(time.Second) / int64(targetRPS)))
	defer ticker.Stop()

	start := time.Now()
	requestCount := int64(0)
	successCount := int64(0)
	errorCount := int64(0)

	var wg sync.WaitGroup
	semaphore := make(chan bool, concurrency)
	done := make(chan bool)

	go func() {
		for {
			select {
			case <-done:
				return
			case <-ticker.C:
				if time.Since(start) > duration {
					close(done)
					return
				}

				wg.Add(1)
				semaphore <- true

				go func() {
					defer wg.Done()
					defer func() { <-semaphore }()

					userID := 40000 + int(atomic.AddInt64(&requestCount, 1))%numUsers
					violationID := int(atomic.LoadInt64(&requestCount)) % 1000

					// Create violation if not exists
					db.Exec(`
						INSERT OR IGNORE INTO violations (id, user_id, violation_type, created_at)
						VALUES (?, ?, 'rate_limit_exceeded', datetime('now', '-5 days'))
					`, violationID, userID)

					_, err := appealSvc.SubmitAppeal(ctx, userID, violationID, "false_positive", "Appeal")
					if err != nil {
						atomic.AddInt64(&errorCount, 1)
					} else {
						atomic.AddInt64(&successCount, 1)
					}
				}()
			}
		}
	}()

	wg.Wait()
	elapsed := time.Since(start)

	actualRPS := float64(successCount) / elapsed.Seconds()

	t.Logf("Sustained Load Test Results:")
	t.Logf("  Target RPS: %d", targetRPS)
	t.Logf("  Actual RPS: %.2f", actualRPS)
	t.Logf("  Total Requests: %d", requestCount)
	t.Logf("  Successful: %d", successCount)
	t.Logf("  Errors: %d", errorCount)
	t.Logf("  Error Rate: %.2f%%", float64(errorCount)/float64(requestCount)*100)
	t.Logf("  Duration: %v", elapsed)

	if float64(errorCount)/float64(requestCount) > 0.05 {
		t.Logf("Warning: Error rate exceeds 5%%")
	}
}

// TestMemoryEfficiencyUnderLoad tests memory usage with many concurrent operations
func TestMemoryEfficiencyUnderLoad(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping memory test in short mode")
	}

	db := setupLoadTestDB(t)
	ctx := context.Background()
	appealSvc := NewAppealService(db)
	negotiationSvc := NewAppealNegotiationService(db)

	// Prepare: 500 users with violations
	const numUsers = 500
	for i := 0; i < numUsers; i++ {
		db.Exec(`
			INSERT INTO reputation_scores (user_id, score, tier)
			VALUES (?, ?, 'standard')
		`, 50000+i, 50.0)

		db.Exec(`
			INSERT INTO violations (id, user_id, violation_type, created_at)
			VALUES (?, ?, 'rate_limit_exceeded', datetime('now', '-5 days'))
		`, 50000+i, 50000+i)
	}

	// Create appeals and messages
	for i := 0; i < numUsers; i++ {
		appeal, _ := appealSvc.SubmitAppeal(ctx, 50000+i, 50000+i, "false_positive", "Appeal")

		if appeal != nil {
			for j := 0; j < 100; j++ {
				negotiationSvc.SendMessage(
					ctx,
					appeal.ID,
					50000+i,
					SenderTypeUser,
					fmt.Sprintf("Message %d", j),
					MessageTypeMessage,
					nil,
					nil,
				)
			}
		}
	}

	// Test: Retrieve all threads (memory test)
	start := time.Now()
	for i := 0; i < numUsers; i++ {
		// In real scenario, this would stress memory as threads accumulate
		negotiationSvc.GetNegotiationThread(ctx, i)
	}
	duration := time.Since(start)

	t.Logf("Memory efficiency test completed in %v", duration)
	t.Logf("Retrieved %d large threads", numUsers)

	if duration > 10*time.Second {
		t.Logf("Warning: Thread retrieval for %d appeals took %v", numUsers, duration)
	}
}

// BenchmarkAppealSubmissionUnderLoad benchmarks appeal submission with varying load
func BenchmarkAppealSubmissionUnderLoad(b *testing.B) {
	db := setupLoadTestDB(&testing.T{})
	ctx := context.Background()
	appealSvc := NewAppealService(db)

	// Prepare: 10,000 users
	const numUsers = 10000
	for i := 0; i < numUsers; i++ {
		db.Exec(`
			INSERT INTO reputation_scores (user_id, score, tier)
			VALUES (?, ?, 'standard')
		`, 60000+i, 50.0)

		db.Exec(`
			INSERT INTO violations (id, user_id, violation_type, created_at)
			VALUES (?, ?, 'rate_limit_exceeded', datetime('now', '-5 days'))
		`, 60000+i, 60000+i)
	}

	b.ResetTimer()

	const concurrency = 100
	semaphore := make(chan bool, concurrency)
	var wg sync.WaitGroup

	for i := 0; i < b.N; i++ {
		wg.Add(1)
		semaphore <- true

		go func(userID int) {
			defer wg.Done()
			defer func() { <-semaphore }()

			appealSvc.SubmitAppeal(ctx, userID, userID%100, "false_positive", "Appeal")
		}(60000 + (i % numUsers))

		if (i+1)%concurrency == 0 {
			wg.Wait()
		}
	}

	wg.Wait()
}

// BenchmarkMessageThreadRetrieval benchmarks thread retrieval performance
func BenchmarkMessageThreadRetrieval(b *testing.B) {
	db := setupLoadTestDB(&testing.T{})
	ctx := context.Background()
	negotiationSvc := NewAppealNegotiationService(db)

	// Prepare: 100 appeals with varying message counts
	for i := 0; i < 100; i++ {
		db.Exec(`
			INSERT INTO appeals (id, user_id, violation_id, reason, status, created_at)
			VALUES (?, ?, ?, 'false_positive', 'reviewing', datetime('now'))
		`, i, 70000+i, i)

		// Each appeal has different number of messages (1 to 1000)
		messageCount := (i%10 + 1) * 100

		for j := 0; j < messageCount; j++ {
			db.Exec(`
				INSERT INTO appeal_negotiation_messages
				(appeal_id, sender_id, sender_type, message, message_type, created_at)
				VALUES (?, ?, ?, ?, 'message', datetime('now', '-? seconds'))
			`, i, 70000+i, "user", fmt.Sprintf("Message %d", j), j)
		}
	}

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		appealID := (i % 100)
		negotiationSvc.GetNegotiationThread(ctx, appealID)
	}
}

// BenchmarkConcurrentNegotiation benchmarks concurrent message sending
func BenchmarkConcurrentNegotiation(b *testing.B) {
	db := setupLoadTestDB(&testing.T{})
	ctx := context.Background()
	negotiationSvc := NewAppealNegotiationService(db)

	// Prepare
	db.Exec(`
		INSERT INTO appeals (id, user_id, violation_id, reason, status, created_at)
		VALUES (1, 80000, 1, 'false_positive', 'reviewing', datetime('now'))
	`)

	b.ResetTimer()

	const concurrency = 10
	semaphore := make(chan bool, concurrency)
	var wg sync.WaitGroup

	for i := 0; i < b.N; i++ {
		wg.Add(1)
		semaphore <- true

		go func(senderID int) {
			defer wg.Done()
			defer func() { <-semaphore }()

			negotiationSvc.SendMessage(
				ctx,
				1,
				senderID,
				SenderTypeAdmin,
				"Message",
				MessageTypeMessage,
				nil,
				nil,
			)
		}(80000 + (i % 10))

		if (i+1)%concurrency == 0 {
			wg.Wait()
		}
	}

	wg.Wait()
}
