package legacy

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jgirmay/GAIA_GO/pkg/models"
)

// RequestTranslator converts legacy Python request format to GAIA_GO format
type RequestTranslator struct {
	strictMode bool
}

// NewRequestTranslator creates a new request translator
func NewRequestTranslator() *RequestTranslator {
	return &RequestTranslator{
		strictMode: false,
	}
}

// TranslateSessionCreate converts legacy session creation request to ClaudeSession
func (rt *RequestTranslator) TranslateSessionCreate(legacyData map[string]interface{}) (*models.ClaudeSession, error) {
	session := &models.ClaudeSession{
		ID:        uuid.New(),
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
		Status:    "idle",
		Metadata:  json.RawMessage([]byte("{}")),
	}

	// Required fields
	if name, ok := legacyData["session_name"].(string); ok {
		session.SessionName = name
	} else if name, ok := legacyData["name"].(string); ok {
		session.SessionName = name
	} else {
		return nil, fmt.Errorf("session_name is required")
	}

	// Optional fields
	if userIDStr, ok := legacyData["user_id"].(string); ok {
		if userID, err := uuid.Parse(userIDStr); err == nil {
			session.UserID = &userID
		}
	}

	if status, ok := legacyData["status"].(string); ok && status != "" {
		session.Status = status
	}

	if tier, ok := legacyData["tier"].(string); ok {
		session.Tier = tier
	}

	if provider, ok := legacyData["provider"].(string); ok {
		session.Provider = provider
	}

	// Handle metadata
	metadata := make(map[string]interface{})
	if meta, ok := legacyData["metadata"].(map[string]interface{}); ok {
		metadata = meta
	}

	// Store any extra fields in metadata
	for key, value := range legacyData {
		if !rt.isKnownSessionField(key) {
			metadata[key] = value
		}
	}

	// Convert metadata to JSON
	if metaBytes, err := json.Marshal(metadata); err == nil {
		session.Metadata = metaBytes
	}

	return session, nil
}

// TranslateSessionUpdate converts legacy session update request
func (rt *RequestTranslator) TranslateSessionUpdate(session *models.ClaudeSession, legacyData map[string]interface{}) *models.ClaudeSession {
	updated := *session
	updated.UpdatedAt = time.Now()

	// Updatable fields
	if name, ok := legacyData["session_name"].(string); ok && name != "" {
		updated.SessionName = name
	} else if name, ok := legacyData["name"].(string); ok && name != "" {
		updated.SessionName = name
	}

	if status, ok := legacyData["status"].(string); ok && status != "" {
		updated.Status = status
	}

	if tier, ok := legacyData["tier"].(string); ok && tier != "" {
		updated.Tier = tier
	}

	if provider, ok := legacyData["provider"].(string); ok && provider != "" {
		updated.Provider = provider
	}

	// Update metadata
	metadata := make(map[string]interface{})
	if len(session.Metadata) > 0 {
		json.Unmarshal(session.Metadata, &metadata)
	}

	if newMetadata, ok := legacyData["metadata"].(map[string]interface{}); ok {
		for key, value := range newMetadata {
			metadata[key] = value
		}
	}

	// Store extra fields
	for key, value := range legacyData {
		if !rt.isKnownSessionField(key) && key != "metadata" {
			metadata[key] = value
		}
	}

	if metaBytes, err := json.Marshal(metadata); err == nil {
		updated.Metadata = metaBytes
	}

	return &updated
}

// TranslateLessonCreate converts legacy lesson creation request
func (rt *RequestTranslator) TranslateLessonCreate(legacyData map[string]interface{}) (*models.Lesson, error) {
	lesson := &models.Lesson{
		ID:        uuid.New(),
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
		Status:    "pending",
		Metadata:  json.RawMessage([]byte("{}")),
	}

	// Required fields
	if title, ok := legacyData["title"].(string); ok {
		lesson.Title = title
	} else {
		return nil, fmt.Errorf("title is required")
	}

	// Optional fields
	if description, ok := legacyData["description"].(string); ok {
		lesson.Description = description
	}

	if status, ok := legacyData["status"].(string); ok {
		lesson.Status = status
	}

	if priority, ok := legacyData["priority"].(float64); ok {
		lesson.Priority = int(priority)
	}

	// Metadata
	metadata := make(map[string]interface{})
	if meta, ok := legacyData["metadata"].(map[string]interface{}); ok {
		metadata = meta
	}

	// Store extra fields
	for key, value := range legacyData {
		if !rt.isKnownLessonField(key) {
			metadata[key] = value
		}
	}

	if metaBytes, err := json.Marshal(metadata); err == nil {
		lesson.Metadata = metaBytes
	}

	return lesson, nil
}

// TranslateLessonUpdate converts legacy lesson update request
func (rt *RequestTranslator) TranslateLessonUpdate(lesson *models.Lesson, legacyData map[string]interface{}) *models.Lesson {
	updated := *lesson
	updated.UpdatedAt = time.Now()

	if title, ok := legacyData["title"].(string); ok && title != "" {
		updated.Title = title
	}

	if description, ok := legacyData["description"].(string); ok {
		updated.Description = description
	}

	if status, ok := legacyData["status"].(string); ok && status != "" {
		updated.Status = status
	}

	if priority, ok := legacyData["priority"].(float64); ok {
		updated.Priority = int(priority)
	}

	// Update metadata
	metadata := make(map[string]interface{})
	if len(lesson.Metadata) > 0 {
		json.Unmarshal(lesson.Metadata, &metadata)
	}

	if newMetadata, ok := legacyData["metadata"].(map[string]interface{}); ok {
		for key, value := range newMetadata {
			metadata[key] = value
		}
	}

	// Store extra fields
	for key, value := range legacyData {
		if !rt.isKnownLessonField(key) && key != "metadata" {
			metadata[key] = value
		}
	}

	if metaBytes, err := json.Marshal(metadata); err == nil {
		updated.Metadata = metaBytes
	}

	return &updated
}

// Helper methods

func (rt *RequestTranslator) isKnownSessionField(field string) bool {
	knownFields := map[string]bool{
		"session_name": true,
		"name":         true,
		"status":       true,
		"user_id":      true,
		"tier":         true,
		"provider":     true,
		"created_at":   true,
		"updated_at":   true,
		"metadata":     true,
		"id":           true,
	}
	return knownFields[field]
}

func (rt *RequestTranslator) isKnownLessonField(field string) bool {
	knownFields := map[string]bool{
		"title":       true,
		"description": true,
		"status":      true,
		"priority":    true,
		"created_at":  true,
		"updated_at":  true,
		"metadata":    true,
		"id":          true,
	}
	return knownFields[field]
}

// ValidateLegacyRequest checks if a request has required fields
func (rt *RequestTranslator) ValidateLegacyRequest(method string, endpoint string, body map[string]interface{}) []string {
	errors := make([]string, 0)

	if method == "POST" {
		if endpoint == "/api/sessions" {
			if _, ok := body["session_name"]; !ok {
				if _, ok := body["name"]; !ok {
					errors = append(errors, "session_name or name is required")
				}
			}
		} else if endpoint == "/api/lessons" {
			if _, ok := body["title"]; !ok {
				errors = append(errors, "title is required")
			}
		}
	}

	return errors
}
