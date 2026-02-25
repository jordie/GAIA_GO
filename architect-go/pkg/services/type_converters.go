package services

import (
	"architect-go/pkg/models"
	"encoding/json"
	"fmt"
	"time"
)

// ==================== WEBHOOK CONVERTERS ====================

// mapToWebhook converts a generic map to a Webhook model
func mapToWebhook(m map[string]interface{}) *models.Webhook {
	webhook := &models.Webhook{}

	if id, ok := m["id"].(string); ok {
		webhook.ID = id
	}
	if projectID, ok := m["project_id"].(string); ok {
		webhook.ProjectID = projectID
	}
	if url, ok := m["url"].(string); ok {
		webhook.URL = url
	}
	if active, ok := m["active"].(bool); ok {
		webhook.Active = active
	}

	// Handle events array - store as JSON
	if events, ok := m["events"].([]interface{}); ok {
		eventStrs := make([]string, 0, len(events))
		for _, e := range events {
			if s, ok := e.(string); ok {
				eventStrs = append(eventStrs, s)
			}
		}
		if data, err := json.Marshal(eventStrs); err == nil {
			webhook.Events = data
		}
	}

	// Parse timestamps
	if createdAt, ok := m["created_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, createdAt); err == nil {
			webhook.CreatedAt = t
		}
	}
	if updatedAt, ok := m["updated_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, updatedAt); err == nil {
			webhook.UpdatedAt = t
		}
	}

	return webhook
}

// webhookToMap converts a Webhook model to a generic map
func webhookToMap(w *models.Webhook) map[string]interface{} {
	// Decode events from JSON
	var events []string
	if len(w.Events) > 0 {
		_ = json.Unmarshal(w.Events, &events)
	}

	return map[string]interface{}{
		"id":         w.ID,
		"project_id": w.ProjectID,
		"url":        w.URL,
		"events":     events,
		"active":     w.Active,
		"created_at": w.CreatedAt.Format(time.RFC3339),
		"updated_at": w.UpdatedAt.Format(time.RFC3339),
	}
}

// ==================== AUDIT LOG CONVERTERS ====================

// mapToAuditLog converts a generic map to an AuditLog model
func mapToAuditLog(m map[string]interface{}) *models.AuditLog {
	auditLog := &models.AuditLog{}

	if id, ok := m["id"].(string); ok {
		auditLog.ID = id
	}
	if action, ok := m["action"].(string); ok {
		auditLog.Action = action
	}
	if userID, ok := m["user_id"].(string); ok {
		auditLog.UserID = userID
	}
	if resource, ok := m["resource"].(string); ok {
		auditLog.Resource = resource
	}
	if resourceID, ok := m["resource_id"].(string); ok {
		auditLog.ResourceID = resourceID
	}
	if changes, ok := m["changes"].(string); ok {
		auditLog.Changes = []byte(changes)
	}
	if status, ok := m["status"].(string); ok {
		auditLog.Status = status
	}

	// Parse timestamps
	if timestamp, ok := m["timestamp"].(string); ok {
		if t, err := time.Parse(time.RFC3339, timestamp); err == nil {
			auditLog.Timestamp = t
		}
	}
	if createdAt, ok := m["created_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, createdAt); err == nil {
			auditLog.CreatedAt = t
		}
	}

	return auditLog
}

// auditLogToMap converts an AuditLog model to a generic map
func auditLogToMap(al *models.AuditLog) map[string]interface{} {
	changesStr := ""
	if al.Changes != nil {
		changesStr = string(al.Changes)
	}

	return map[string]interface{}{
		"id":         al.ID,
		"action":     al.Action,
		"user_id":    al.UserID,
		"resource":   al.Resource,
		"resource_id": al.ResourceID,
		"changes":    changesStr,
		"status":     al.Status,
		"timestamp":  al.Timestamp.Format(time.RFC3339),
		"created_at": al.CreatedAt.Format(time.RFC3339),
	}
}

// ==================== REALTIME EVENT CONVERTERS ====================

// mapToRealtimeEvent converts a generic map to a RealtimeEvent model (if exists)
func mapToRealtimeEvent(m map[string]interface{}) map[string]interface{} {
	// For now, return the map as-is since models may not have a specific RealtimeEvent type
	// This is a passthrough converter for consistency
	return m
}

// realtimeEventToMap converts a RealtimeEvent to a generic map
func realtimeEventToMap(event map[string]interface{}) map[string]interface{} {
	return event
}

// ==================== INTEGRATION HEALTH CONVERTERS ====================

// mapToHealthCheck converts a generic map to a HealthCheck response
func mapToHealthCheck(m map[string]interface{}) map[string]interface{} {
	healthCheck := make(map[string]interface{})

	if status, ok := m["status"].(string); ok {
		healthCheck["status"] = status
	}
	if message, ok := m["message"].(string); ok {
		healthCheck["message"] = message
	}
	if timestamp, ok := m["timestamp"].(string); ok {
		healthCheck["timestamp"] = timestamp
	}
	if metrics, ok := m["metrics"].(map[string]interface{}); ok {
		healthCheck["metrics"] = metrics
	}

	return healthCheck
}

// ==================== HELPER CONVERTERS ====================

// jsonBytesToMap unmarshals JSON bytes to a map
func jsonBytesToMap(data []byte) (map[string]interface{}, error) {
	var m map[string]interface{}
	if err := json.Unmarshal(data, &m); err != nil {
		return nil, fmt.Errorf("failed to unmarshal JSON: %w", err)
	}
	return m, nil
}

// mapToJSONBytes marshals a map to JSON bytes
func mapToJSONBytes(m map[string]interface{}) ([]byte, error) {
	data, err := json.Marshal(m)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal map to JSON: %w", err)
	}
	return data, nil
}

// convertStringSliceToInterface converts []string to []interface{}
func convertStringSliceToInterface(strs []string) []interface{} {
	result := make([]interface{}, len(strs))
	for i, s := range strs {
		result[i] = s
	}
	return result
}

// convertInterfaceSliceToString converts []interface{} to []string
func convertInterfaceSliceToString(ifaces []interface{}) []string {
	result := make([]string, 0, len(ifaces))
	for _, i := range ifaces {
		if s, ok := i.(string); ok {
			result = append(result, s)
		}
	}
	return result
}

// ==================== BATCH CONVERTERS ====================

// mapsToWebhooks converts a slice of maps to a slice of Webhook pointers
func mapsToWebhooks(maps []map[string]interface{}) []*models.Webhook {
	webhooks := make([]*models.Webhook, len(maps))
	for i, m := range maps {
		webhooks[i] = mapToWebhook(m)
	}
	return webhooks
}

// webhooksToMaps converts a slice of Webhook pointers to a slice of maps
func webhooksToMaps(webhooks []*models.Webhook) []map[string]interface{} {
	maps := make([]map[string]interface{}, len(webhooks))
	for i, w := range webhooks {
		maps[i] = webhookToMap(w)
	}
	return maps
}

// mapsToAuditLogs converts a slice of maps to a slice of AuditLog pointers
func mapsToAuditLogs(maps []map[string]interface{}) []*models.AuditLog {
	logs := make([]*models.AuditLog, len(maps))
	for i, m := range maps {
		logs[i] = mapToAuditLog(m)
	}
	return logs
}

// auditLogsToMaps converts a slice of AuditLog pointers to a slice of maps
func auditLogsToMaps(logs []*models.AuditLog) []map[string]interface{} {
	maps := make([]map[string]interface{}, len(logs))
	for i, l := range logs {
		maps[i] = auditLogToMap(l)
	}
	return maps
}
