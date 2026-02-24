package api

import (
	"github.com/gin-gonic/gin"
)

// ============================================================================
// BACKWARD COMPATIBILITY ADAPTERS
// ============================================================================
// These functions maintain old response formats during the migration to
// standardized API responses. They should be removed once frontend is migrated.
// See docs/architecture/ARCHITECTURE.md for migration timeline.

// LegacyLeaderboardResponse maintains the old leaderboard response format
// Old format: {"success": true, "leaderboard": [...], "entry_count": N}
// Instead of new format: {"success": true, "data": [...], "count": N}
func LegacyLeaderboardResponse(c *gin.Context, entries interface{}, count int) {
	c.JSON(200, gin.H{
		"success":      true,
		"leaderboard":  entries,
		"entry_count":  count,
	})
}

// RawArrayResponse returns a raw array without wrapper envelope
// Used for endpoints like typing's handleGetUsers that return raw arrays
// Old format: [{...}, {...}]
// New format would be: {"success": true, "data": [...], "count": N}
func RawArrayResponse(c *gin.Context, data interface{}) {
	c.JSON(200, data)
}

// DualTopListResponse maintains the dual top-list response format
// Used for typing leaderboard with top_wpm and top_accuracy lists
// Format: {"top_wpm": [...], "top_accuracy": [...]}
func DualTopListResponse(c *gin.Context, topWPM, topAcc interface{}) {
	c.JSON(200, gin.H{
		"top_wpm":      topWPM,
		"top_accuracy": topAcc,
	})
}

// WarmupListResponse maintains the old warmups response format
// Old format: {"success": true, "warmups": [...], "count": N}
// Instead of new format: {"success": true, "data": [...], "count": N}
func WarmupListResponse(c *gin.Context, warmups interface{}, count int) {
	c.JSON(200, gin.H{
		"success":  true,
		"warmups":  warmups,
		"count":    count,
	})
}

// NoteAnalyticsResponse maintains the old analytics response format
// Old format: {"success": true, "analytics": [...], "count": N}
// Instead of new format: {"success": true, "data": [...], "count": N}
func NoteAnalyticsResponse(c *gin.Context, analytics interface{}, count int) {
	c.JSON(200, gin.H{
		"success":   true,
		"analytics": analytics,
		"count":     count,
	})
}

// GoalsListResponse maintains the old goals response format with count
// Old format: {"success": true, "goals": [...], "count": N}
func GoalsListResponse(c *gin.Context, goals interface{}, count int) {
	c.JSON(200, gin.H{
		"success": true,
		"goals":   goals,
		"count":   count,
	})
}

// BadgesListResponse maintains the old badges response format with count
// Old format: {"success": true, "badges": [...], "count": N}
func BadgesListResponse(c *gin.Context, badges interface{}, count int) {
	c.JSON(200, gin.H{
		"success": true,
		"badges":  badges,
		"count":   count,
	})
}

// StatsNestedResponse for endpoints that return stats in a nested structure
// Old format: {"success": true, "stats": {...}}
func StatsNestedResponse(c *gin.Context, stats interface{}) {
	c.JSON(200, gin.H{
		"success": true,
		"stats":   stats,
	})
}

// AnalyticsNestedResponse for endpoints that return analytics in nested structure
// Old format: {"success": true, "analytics": {...}}
func AnalyticsNestedResponse(c *gin.Context, analytics interface{}) {
	c.JSON(200, gin.H{
		"success":   true,
		"analytics": analytics,
	})
}

// MasteryResponse maintains old word mastery response format
// Old format: {"success": true, "mastery": {...}}
func MasteryResponse(c *gin.Context, mastery interface{}) {
	c.JSON(200, gin.H{
		"success": true,
		"mastery": mastery,
	})
}

// WordsListResponse maintains old words response format
// Old format: {"success": true, "words": [...], "count": N}
func WordsListResponse(c *gin.Context, words interface{}, count int) {
	c.JSON(200, gin.H{
		"success": true,
		"words":   words,
		"count":   count,
	})
}
