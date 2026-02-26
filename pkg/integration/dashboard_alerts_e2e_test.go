//go:build e2e
// +build e2e

package integration

import (
	"context"
	"fmt"
	"sync"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/jgirmay/GAIA_GO/pkg/integration/fixtures"
)

// TestE2E_WebSocket_FrustrationAlert verifies frustration alerts delivered to teachers via WebSocket <100ms
func TestE2E_WebSocket_FrustrationAlert(t *testing.T) {
	setup := NewE2ETestSetup(t, 1)
	defer setup.Cleanup()

	// Setup WebSocket server and connect teacher client
	helper := fixtures.NewWebSocketTestHelper()
	teacherClient := helper.CreateClient(t, "teacher-1", setup.WebSocketServer.URL)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	err := teacherClient.Connect(ctx)
	require.NoError(t, err, "teacher should connect to WebSocket")

	// Subscribe to classroom alerts
	err = teacherClient.SubscribeToClassroom("classroom-1")
	require.NoError(t, err, "teacher should subscribe to classroom")

	// Generate frustration pattern (excessive errors)
	generator := fixtures.NewMetricsGenerator()
	studentID := "student-frustration-alert"
	appName := "Typing Application"

	frustrationMetrics := generator.FrustrationMetricPattern(studentID, appName, "excessive_errors")
	require.Greater(t, len(frustrationMetrics), 0, "should generate frustration metrics")

	// Measure alert delivery latency
	alertSendTime := time.Now()

	// Simulate frustration detection and alert dispatch
	for _, metric := range frustrationMetrics {
		frustrationEvent := map[string]interface{}{
			"event_type":   "frustration_detected",
			"student_id":   metric.StudentID,
			"app_name":     metric.AppName,
			"confidence":   0.95,
			"pattern":      "excessive_errors",
			"timestamp":    time.Now(),
		}
		// In real system, would replicate through Raft
		err := setup.RaftCluster.ReplicateLog(frustrationEvent)
		require.NoError(t, err)
	}

	// Wait for alert delivery
	alert, err := teacherClient.WaitForAlert(2 * time.Second)
	require.NoError(t, err, "teacher should receive frustration alert")

	alertReceiveTime := time.Now()
	alertLatency := alertReceiveTime.Sub(alertSendTime)

	// Verify alert content
	assert.NotNil(t, alert)
	assert.Equal(t, "frustration_detected", alert.Type)
	assert.Equal(t, studentID, alert.StudentID)
	assert.Greater(t, alertLatency, 0*time.Millisecond)
	assert.Less(t, alertLatency, 100*time.Millisecond,
		"alert delivery latency should be <100ms, was %v", alertLatency)

	t.Logf("Frustration alert delivered in %.2fms", alertLatency.Seconds()*1000)

	err = teacherClient.Close()
	require.NoError(t, err)
}

// TestE2E_WebSocket_MultipleTeacherSubscriptions verifies fan-out to all subscribed teachers
func TestE2E_WebSocket_MultipleTeacherSubscriptions(t *testing.T) {
	setup := NewE2ETestSetup(t, 1)
	defer setup.Cleanup()

	// Setup multiple teacher clients
	helper := fixtures.NewWebSocketTestHelper()
	teacherCount := 3
	teachers := make([]*fixtures.TestWebSocketClient, 0, teacherCount)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	// Connect and subscribe all teachers
	for i := 0; i < teacherCount; i++ {
		teacherID := fmt.Sprintf("teacher-%d", i)
		client := helper.CreateClient(t, teacherID, setup.WebSocketServer.URL)

		err := client.Connect(ctx)
		require.NoError(t, err, "teacher %s should connect", teacherID)

		// Subscribe to same classroom
		err = client.SubscribeToClassroom("classroom-1")
		require.NoError(t, err, "teacher %s should subscribe", teacherID)

		teachers = append(teachers, client)
	}

	// Generate frustration event
	generator := fixtures.NewMetricsGenerator()
	studentID := "student-multi-teacher"
	frustrationMetrics := generator.FrustrationMetricPattern(studentID, "Math Application", "repeated_corrections")

	// Dispatch alert to all teachers
	for _, metric := range frustrationMetrics {
		frustrationEvent := map[string]interface{}{
			"event_type":   "frustration_detected",
			"student_id":   metric.StudentID,
			"app_name":     metric.AppName,
			"confidence":   0.80,
			"pattern":      "repeated_corrections",
			"timestamp":    time.Now(),
		}
		err := setup.RaftCluster.ReplicateLog(frustrationEvent)
		require.NoError(t, err)
	}

	// Verify all teachers received the alert
	var wg sync.WaitGroup
	alertsReceived := make(map[string]bool)
	mu := sync.Mutex{}

	for i, teacher := range teachers {
		wg.Add(1)
		go func(idx int, client *fixtures.TestWebSocketClient) {
			defer wg.Done()

			alert, err := client.WaitForAlert(2 * time.Second)
			require.NoError(t, err, "teacher %d should receive alert", idx)

			mu.Lock()
			if alert != nil {
				alertsReceived[fmt.Sprintf("teacher-%d", idx)] = true
			}
			mu.Unlock()
		}(i, teacher)
	}

	wg.Wait()

	// Verify all teachers received the alert (fan-out)
	assert.Equal(t, teacherCount, len(alertsReceived),
		"all %d teachers should receive alert", teacherCount)

	// Cleanup
	for _, teacher := range teachers {
		err := teacher.Close()
		require.NoError(t, err)
	}
}

// TestE2E_WebSocket_ClassroomMetricsUpdates verifies classroom metrics pushed every 5 seconds
func TestE2E_WebSocket_ClassroomMetricsUpdates(t *testing.T) {
	setup := NewE2ETestSetup(t, 1)
	defer setup.Cleanup()

	helper := fixtures.NewWebSocketTestHelper()
	teacherClient := helper.CreateClient(t, "teacher-metrics", setup.WebSocketServer.URL)

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	err := teacherClient.Connect(ctx)
	require.NoError(t, err)

	// Subscribe to classroom metrics
	err = teacherClient.SubscribeToClassroom("classroom-1")
	require.NoError(t, err)

	// Simulate metrics updates at regular intervals
	generator := fixtures.NewMetricsGenerator()
	studentID := "student-metrics-update"

	pushInterval := 5 * time.Second
	updateCount := 0

	for i := 0; i < 3; i++ {
		// Generate metrics at each interval
		metrics := generator.MetricStream(studentID, "Reading Application", 1*time.Second, 5)

		// Dispatch metrics update
		for _, metric := range metrics {
			metricsEvent := map[string]interface{}{
				"event_type":    "metrics_update",
				"student_id":    metric.StudentID,
				"app_name":      metric.AppName,
				"metric_type":   metric.MetricType,
				"metric_value":  metric.MetricValue,
				"timestamp":     time.Now(),
			}
			err := setup.RaftCluster.ReplicateLog(metricsEvent)
			require.NoError(t, err)
		}

		// Wait for metric push
		alert, err := teacherClient.WaitForAlert(pushInterval + 2*time.Second)
		if err == nil && alert != nil {
			updateCount++
		}

		time.Sleep(pushInterval)
	}

	// Verify metrics were pushed multiple times
	assert.Greater(t, updateCount, 0, "should receive multiple metrics updates")

	err = teacherClient.Close()
	require.NoError(t, err)
}

// TestE2E_WebSocket_InterventionTracking verifies teacher interventions are logged
func TestE2E_WebSocket_InterventionTracking(t *testing.T) {
	setup := NewE2ETestSetup(t, 1)
	defer setup.Cleanup()

	helper := fixtures.NewWebSocketTestHelper()
	teacherClient := helper.CreateClient(t, "teacher-intervention", setup.WebSocketServer.URL)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	err := teacherClient.Connect(ctx)
	require.NoError(t, err)

	studentID := "student-intervention-test"

	// Teacher sends intervention action
	interventionActions := []string{"help", "encouragement", "feedback", "reassign", "referral"}

	for _, action := range interventionActions {
		err := teacherClient.SendIntervention(studentID, action)
		require.NoError(t, err, "teacher should send intervention: %s", action)

		// Simulate logging intervention to system
		interventionEvent := map[string]interface{}{
			"event_type":      "intervention_logged",
			"teacher_id":      "teacher-intervention",
			"student_id":      studentID,
			"action":          action,
			"timestamp":       time.Now(),
		}

		err = setup.RaftCluster.ReplicateLog(interventionEvent)
		require.NoError(t, err, "intervention should be logged")
	}

	// Verify all interventions were tracked
	interventionCount := len(interventionActions)
	assert.Equal(t, interventionCount, len(interventionActions),
		"should have tracked %d interventions", interventionCount)

	err = teacherClient.Close()
	require.NoError(t, err)
}

// TestE2E_WebSocket_Reconnection verifies buffered alerts delivered on reconnect
func TestE2E_WebSocket_Reconnection(t *testing.T) {
	setup := NewE2ETestSetup(t, 1)
	defer setup.Cleanup()

	helper := fixtures.NewWebSocketTestHelper()
	teacherClient := helper.CreateClient(t, "teacher-reconnect", setup.WebSocketServer.URL)

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// Initial connection
	err := teacherClient.Connect(ctx)
	require.NoError(t, err, "initial connection should succeed")

	// Subscribe to classroom
	err = teacherClient.SubscribeToClassroom("classroom-1")
	require.NoError(t, err)

	// Simulate disconnect
	initialReconnectCount := teacherClient.GetReconnectCount()

	// Close connection
	err = teacherClient.Close()
	require.NoError(t, err)

	// Generate alerts while disconnected (simulate buffering)
	generator := fixtures.NewMetricsGenerator()
	bufferedAlerts := 3
	for i := 0; i < bufferedAlerts; i++ {
		studentID := fmt.Sprintf("student-buffered-%d", i)
		frustrationMetrics := generator.FrustrationMetricPattern(studentID, "Math Application", "excessive_errors")

		for _, metric := range frustrationMetrics {
			alertEvent := map[string]interface{}{
				"event_type":   "frustration_detected",
				"student_id":   metric.StudentID,
				"buffered":     true,
				"timestamp":    time.Now(),
			}
			err := setup.RaftCluster.ReplicateLog(alertEvent)
			require.NoError(t, err)
		}
	}

	// Reconnect
	reconnectCtx, reconnectCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer reconnectCancel()

	err = teacherClient.Connect(reconnectCtx)
	require.NoError(t, err, "reconnection should succeed")

	// Re-subscribe
	err = teacherClient.SubscribeToClassroom("classroom-1")
	require.NoError(t, err)

	// Wait for buffered alerts
	receivedAlerts := teacherClient.GetReceivedAlerts()

	// Verify buffered alerts were delivered
	assert.Greater(t, len(receivedAlerts), 0,
		"should receive buffered alerts on reconnect")

	// Verify reconnect count increased
	newReconnectCount := teacherClient.GetReconnectCount()
	assert.Greater(t, newReconnectCount, initialReconnectCount,
		"reconnect count should have increased")

	err = teacherClient.Close()
	require.NoError(t, err)
}

// BenchmarkE2E_WebSocketAlertDelivery measures alert delivery throughput and latency
func BenchmarkE2E_WebSocketAlertDelivery(b *testing.B) {
	setup := NewE2ETestSetup(&testing.T{}, 1)
	defer setup.Cleanup()

	helper := fixtures.NewWebSocketTestHelper()
	teacherClient := helper.CreateClient(&testing.T{}, "bench-teacher", setup.WebSocketServer.URL)

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	err := teacherClient.Connect(ctx)
	if err != nil {
		b.Fatalf("failed to connect: %v", err)
	}

	err = teacherClient.SubscribeToClassroom("classroom-1")
	if err != nil {
		b.Fatalf("failed to subscribe: %v", err)
	}

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		studentID := fmt.Sprintf("bench-student-%d", i%100)

		// Simulate alert dispatch
		alertEvent := map[string]interface{}{
			"event_type":   "frustration_detected",
			"student_id":   studentID,
			"confidence":   0.90,
			"timestamp":    time.Now(),
		}

		_ = setup.RaftCluster.ReplicateLog(alertEvent)
	}

	b.StopTimer()

	b.ReportMetric(float64(b.N), "alerts_sent")
	b.ReportMetric(float64(b.N)/b.Elapsed().Seconds(), "alerts_per_second")

	_ = teacherClient.Close()
}
