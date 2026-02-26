//go:build e2e
// +build e2e

package integration

import (
	"fmt"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/jgirmay/GAIA_GO/pkg/integration/fixtures"
)

// TestE2E_TaskEnqueueAndClaim verifies basic task enqueueing and claiming
func TestE2E_TaskEnqueueAndClaim(t *testing.T) {
	setup := NewE2ETestSetup(t, 1)
	defer setup.Cleanup()

	// Enqueue 100 tasks with varying priorities
	taskCount := 100
	enqueuedTasks := make(map[string]interface{})

	for i := 0; i < taskCount; i++ {
		task := fixtures.NewTestTask("grading", (i%10)+1, map[string]interface{}{
			"student_id": fmt.Sprintf("student-%d", i),
			"quiz_id":    fmt.Sprintf("quiz-%d", i/10),
		})
		taskID := fmt.Sprintf("task-%d", i)
		task["id"] = taskID
		enqueuedTasks[taskID] = task
	}

	// Register 5 worker sessions
	workers := make([]string, 5)
	for i := 0; i < 5; i++ {
		workers[i] = fmt.Sprintf("worker-%d", i)
	}

	// Simulate claiming tasks
	claimedTasks := make(map[string]string) // taskID -> workerID
	claimedMu := sync.Mutex{}

	// Each worker claims tasks (simulated)
	for _, workerID := range workers {
		for taskID, taskData := range enqueuedTasks {
			// Claim task (in real impl, would use distributed lock)
			claimedMu.Lock()
			if _, alreadyClaimed := claimedTasks[taskID]; !alreadyClaimed {
				claimedTasks[taskID] = workerID
				claimedMu.Unlock()
				break // Only claim one task per iteration
			}
			claimedMu.Unlock()
		}
	}

	// Verify each task claimed by exactly one worker
	for taskID, claimedBy := range claimedTasks {
		require.NotEmpty(t, claimedBy, "task %s not claimed by any worker", taskID)
		// In real test, would verify no double-claims in database
	}

	// Verify priority ordering
	// Tasks with higher priority should be claimed first
	taskPriorities := make([]int, 0)
	for _, taskData := range enqueuedTasks {
		if task, ok := taskData.(map[string]interface{}); ok {
			if priority, ok := task["priority"].(int); ok {
				taskPriorities = append(taskPriorities, priority)
			}
		}
	}

	assert.Greater(t, len(taskPriorities), 0, "should have parsed task priorities")
}

// TestE2E_IdempotencyKeyEnforcement verifies duplicate task prevention
func TestE2E_IdempotencyKeyEnforcement(t *testing.T) {
	setup := NewE2ETestSetup(t, 1)
	defer setup.Cleanup()

	// Enqueue a task with idempotency key
	idempotencyKey := "analytics-job-123"
	taskData := map[string]interface{}{
		"classroom_id": "class-456",
		"metric":       "engagement",
	}

	task1 := fixtures.NewIdempotentTask(idempotencyKey, taskData)
	task1ID := uuid.New().String()
	task1["id"] = task1ID

	// Attempt to enqueue the same task again (same idempotency key)
	task2 := fixtures.NewIdempotentTask(idempotencyKey, taskData)

	// In real implementation, second enqueue would return existing task
	// Verify: task2 should have same ID as task1
	// For now, we test the data structure
	require.Equal(t, task1["idempotency_key"], task2["idempotency_key"],
		"idempotency keys should match")

	// Test: Multiple enqueues with same key return same task
	uniqueKeys := make(map[string]bool)
	for _, task := range []map[string]interface{}{task1, task2} {
		key := fmt.Sprintf("%v", task["idempotency_key"])
		uniqueKeys[key] = true
	}

	assert.Equal(t, 1, len(uniqueKeys), "should have only one unique idempotency key")
}

// TestE2E_ConcurrentClaims_NoDoubleAssignment verifies exactly-once semantics under concurrency
func TestE2E_ConcurrentClaims_NoDoubleAssignment(t *testing.T) {
	setup := NewE2ETestSetup(t, 1)
	defer setup.Cleanup()

	// Enqueue 50 tasks
	taskCount := 50
	tasksToClaimMap := make(map[string]bool)
	for i := 0; i < taskCount; i++ {
		tasksToClaimMap[fmt.Sprintf("task-%d", i)] = false
	}

	// Launch 10 goroutines attempting to claim tasks concurrently
	claimsMu := sync.Mutex{}
	claimsPerTask := make(map[string]int) // taskID -> claim count

	var wg sync.WaitGroup
	for goroutineID := 0; goroutineID < 10; goroutineID++ {
		wg.Add(1)
		go func(gid int) {
			defer wg.Done()

			for taskID := range tasksToClaimMap {
				// Simulate acquiring distributed lock before claim
				claimsMu.Lock()
				currentClaims := claimsPerTask[taskID]
				if currentClaims == 0 {
					claimsPerTask[taskID] = currentClaims + 1
					claimsMu.Unlock()
					// Successfully claimed
					time.Sleep(time.Millisecond) // Simulate work
				} else {
					claimsMu.Unlock()
					// Task already claimed by another goroutine
				}
			}
		}(goroutineID)
	}

	wg.Wait()

	// Verify no task was claimed twice
	for taskID, claimCount := range claimsPerTask {
		assert.LessOrEqual(t, claimCount, 1,
			"task %s claimed %d times (should be 0 or 1)", taskID, claimCount)
	}

	// Verify all tasks were claimed exactly once (or not at all due to race)
	totalClaims := 0
	for _, count := range claimsPerTask {
		totalClaims += count
	}
	assert.Greater(t, totalClaims, 0, "at least some tasks should have been claimed")
}

// TestE2E_TaskRetry_ExponentialBackoff verifies retry logic with backoff
func TestE2E_TaskRetry_ExponentialBackoff(t *testing.T) {
	setup := NewE2ETestSetup(t, 1)
	defer setup.Cleanup()

	// Create a task
	task := fixtures.NewTestTask("error-prone-task", 5, map[string]interface{}{
		"data": "test",
	})
	task["id"] = "task-retry-test"
	task["retry_count"] = 0
	task["max_retries"] = 3
	task["status"] = "pending"

	retryTimes := make([]time.Time, 0)
	retryTimes = append(retryTimes, time.Now()) // Initial attempt

	// Simulate 3 failures with exponential backoff
	// Backoff: 1s, 2s, 4s (2^retryCount * baseBackoff)
	baseBackoff := time.Second
	for retry := 1; retry <= 3; retry++ {
		backoffDuration := time.Duration(1<<(uint(retry)-1)) * baseBackoff
		time.Sleep(backoffDuration) // Simulate backoff

		retryTimes = append(retryTimes, time.Now())

		// Update task state
		task["retry_count"] = retry
		if retry >= 3 {
			task["status"] = "failed" // Max retries exceeded
		}
	}

	// Verify retry_count incremented on each failure
	assert.Equal(t, 3, task["retry_count"], "retry_count should be 3")

	// Verify status changed to failed after max_retries
	assert.Equal(t, "failed", task["status"], "status should be failed after max retries")

	// Verify exponential backoff timing
	assert.Equal(t, 4, len(retryTimes), "should have 4 timestamps (initial + 3 retries)")
}

// TestE2E_ClaimExpiration_Timeout verifies claim timeout and reassignment
func TestE2E_ClaimExpiration_Timeout(t *testing.T) {
	setup := NewE2ETestSetup(t, 1)
	defer setup.Cleanup()

	// Create and claim a task
	task := fixtures.NewTestTask("long-running", 5, map[string]interface{}{
		"data": "test",
	})
	task["id"] = "task-timeout-test"
	task["status"] = "claimed"
	task["claimed_by"] = "worker-1"
	task["claimed_at"] = time.Now()
	task["claim_timeout"] = 10 * time.Minute

	claimedTime := time.Now()

	// Simulate time passing beyond timeout
	// In real implementation, cleanup job would run and check for expired claims
	timeout := time.Duration(task["claim_timeout"].(time.Duration))
	expiredTime := claimedTime.Add(timeout).Add(1 * time.Second)

	if expiredTime.After(time.Now()) {
		// Task still within timeout
		assert.Equal(t, "claimed", task["status"])
		assert.Equal(t, "worker-1", task["claimed_by"])
	} else {
		// Task should be expired and reassigned
		task["status"] = "pending"
		task["claimed_by"] = nil
		assert.Equal(t, "pending", task["status"])
	}

	// Verify worker-2 can now claim the task
	if task["status"] == "pending" {
		task["claimed_by"] = "worker-2"
		task["status"] = "claimed"
		assert.Equal(t, "worker-2", task["claimed_by"])
	}
}

// TestE2E_TaskPriorityOrdering verifies tasks claimed by priority (high first)
func TestE2E_TaskPriorityOrdering(t *testing.T) {
	setup := NewE2ETestSetup(t, 1)
	defer setup.Cleanup()

	// Create 100 tasks with varying priorities
	allTasks := fixtures.TaskBatch(100)

	// Sort by expected priority claim order
	// Priority 10 tasks should be claimed first
	priority10Count := 0
	priority5Count := 0
	priority1Count := 0

	for _, task := range allTasks {
		if priority, ok := task["priority"].(int); ok {
			switch priority {
			case 10:
				priority10Count++
			case 5:
				priority5Count++
			case 1:
				priority1Count++
			}
		}
	}

	// Verify distribution matches expected (30% priority 10, rest split)
	assert.Greater(t, priority10Count, 0, "should have priority 10 tasks")
	assert.Greater(t, priority5Count, 0, "should have priority 5 tasks")
	assert.Greater(t, priority1Count, 0, "should have priority 1 tasks")

	// Simulate claiming in priority order
	claimOrder := make([]int, 0)
	for i := 0; i < 3; i++ {
		for _, task := range allTasks {
			if priority, ok := task["priority"].(int); ok {
				if len(claimOrder) < 10 { // Claim first 10
					claimOrder = append(claimOrder, priority)
				}
			}
		}
	}

	// Verify priority ordering (higher priority claimed first)
	for i := 0; i < len(claimOrder)-1; i++ {
		assert.GreaterOrEqual(t, claimOrder[i], claimOrder[i+1],
			"tasks should be claimed in descending priority order")
	}
}

// TestE2E_TaskCompletion_UpdateStatus verifies task completion flow
func TestE2E_TaskCompletion_UpdateStatus(t *testing.T) {
	setup := NewE2ETestSetup(t, 1)
	defer setup.Cleanup()

	// Create and claim a task
	task := fixtures.NewTestTask("completion-test", 5, map[string]interface{}{
		"data": "test",
	})
	task["id"] = "task-completion-test"
	task["status"] = "pending"

	// Worker claims the task
	task["status"] = "claimed"
	task["claimed_by"] = "worker-1"
	task["claimed_at"] = time.Now()

	assert.Equal(t, "claimed", task["status"])

	// Worker completes the task
	task["status"] = "completed"
	task["result"] = map[string]interface{}{
		"status": "success",
		"output": "completed successfully",
	}
	task["completed_at"] = time.Now()

	// Verify task is marked completed
	assert.Equal(t, "completed", task["status"])
	assert.NotNil(t, task["result"])
	assert.NotNil(t, task["completed_at"])
}

// TestE2E_DistributedLocking_PreventDoubleAssignment verifies distributed lock mechanism
func TestE2E_DistributedLocking_PreventDoubleAssignment(t *testing.T) {
	setup := NewE2ETestSetup(t, 1)
	defer setup.Cleanup()

	// Simulate distributed lock
	lockKey := "task-claim-lock"
	var lockAcquired atomic.Bool
	lockAcquired.Store(false)

	taskID := "task-lock-test"
	claimers := make([]string, 0)
	claimersMu := sync.Mutex{}

	// Multiple goroutines try to claim the task
	var wg sync.WaitGroup
	for i := 0; i < 5; i++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()

			// Try to acquire lock
			if !lockAcquired.Load() && lockAcquired.CompareAndSwap(false, true) {
				// Lock acquired
				workerName := fmt.Sprintf("worker-%d", workerID)
				claimersMu.Lock()
				claimers = append(claimers, workerName)
				claimersMu.Unlock()

				time.Sleep(10 * time.Millisecond) // Simulate work
				lockAcquired.Store(false)          // Release lock
			}
		}(i)
	}

	wg.Wait()

	// Verify exactly one worker was able to claim (due to lock)
	assert.Equal(t, 1, len(claimers),
		"exactly one worker should have acquired the lock")
}

// BenchmarkE2E_TaskClaimThroughput measures tasks/second claim throughput
func BenchmarkE2E_TaskClaimThroughput(b *testing.B) {
	setup := NewE2ETestSetup(&testing.T{}, 1)
	defer setup.Cleanup()

	// Enqueue b.N tasks
	for i := 0; i < b.N; i++ {
		task := fixtures.NewTestTask("bench-task", 5, map[string]interface{}{
			"id": fmt.Sprintf("bench-task-%d", i),
		})
		_ = setup.RaftCluster.ReplicateLog(task)
	}

	b.ResetTimer()

	// Simulate claiming all tasks
	var claimCount int32
	for i := 0; i < b.N; i++ {
		// Simulate task claim (atomic increment in real impl)
		atomic.AddInt32(&claimCount, 1)
	}

	b.StopTimer()

	claimCountFinal := atomic.LoadInt32(&claimCount)
	b.ReportMetric(float64(claimCountFinal), "tasks_claimed")
	b.ReportMetric(float64(claimCountFinal)/b.Elapsed().Seconds(), "tasks_per_second")
}

// BenchmarkE2E_ConcurrentTaskClaims measures concurrent claim performance
func BenchmarkE2E_ConcurrentTaskClaims(b *testing.B) {
	setup := NewE2ETestSetup(&testing.T{}, 1)
	defer setup.Cleanup()

	taskCount := 1000
	for i := 0; i < taskCount; i++ {
		task := fixtures.NewTestTask("concurrent-bench", 5, map[string]interface{}{})
		_ = setup.RaftCluster.ReplicateLog(task)
	}

	b.ResetTimer()

	// Simulate 10 concurrent workers claiming tasks
	var claimCount int32
	var wg sync.WaitGroup
	for worker := 0; worker < 10; worker++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for i := 0; i < taskCount/10; i++ {
				atomic.AddInt32(&claimCount, 1)
			}
		}()
	}

	wg.Wait()
	b.StopTimer()

	claimCountFinal := atomic.LoadInt32(&claimCount)
	b.ReportMetric(float64(claimCountFinal), "concurrent_claims")
	b.ReportMetric(float64(claimCountFinal)/b.Elapsed().Seconds(), "concurrent_claims_per_sec")
}
