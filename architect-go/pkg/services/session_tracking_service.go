package services

import (
	"context"

	"architect-go/pkg/models"
)

// SessionTrackingService defines session management and monitoring business logic
type SessionTrackingService interface {
	// ListSessions retrieves all sessions (admin)
	ListSessions(ctx context.Context, limit, offset int) ([]*models.Session, int64, error)

	// GetSession retrieves session details
	GetSession(ctx context.Context, id string) (*models.Session, error)

	// GetCurrentSession retrieves current user's session
	GetCurrentSession(ctx context.Context, userID string) (*models.Session, error)

	// CreateSession creates new session (login)
	CreateSession(ctx context.Context, userID string, ipAddress string, userAgent string) (*models.Session, error)

	// DestroySession destroys session (logout)
	DestroySession(ctx context.Context, id string) error

	// DestroyAllUserSessions destroys all sessions for user
	DestroyAllUserSessions(ctx context.Context, userID string) error

	// ExtendSession extends session duration
	ExtendSession(ctx context.Context, id string, req *SessionExtendRequest) error

	// GetUserSessions retrieves all sessions for user
	GetUserSessions(ctx context.Context, userID string, limit, offset int) ([]*models.Session, int64, error)

	// ListActiveSessions retrieves only active sessions
	ListActiveSessions(ctx context.Context, limit, offset int) ([]*models.Session, int64, error)

	// ListInactiveSessions retrieves inactive sessions
	ListInactiveSessions(ctx context.Context, limit, offset int) ([]*models.Session, int64, error)

	// GetSessionStats returns session statistics
	GetSessionStats(ctx context.Context) (*SessionStatsResponse, error)

	// GetConcurrentUserCount retrieves number of concurrent users
	GetConcurrentUserCount(ctx context.Context) (*ConcurrentUserResponse, error)

	// ValidateSession validates if session is still active
	ValidateSession(ctx context.Context, id string) (bool, error)

	// LogActivity logs user activity in session
	LogActivity(ctx context.Context, sessionID string, req *SessionActivityRequest) error

	// GetActivityHistory retrieves activity history for session
	GetActivityHistory(ctx context.Context, sessionID string, limit, offset int) ([]map[string]interface{}, int64, error)

	// GetActivityTimeline retrieves system activity timeline
	GetActivityTimeline(ctx context.Context, limit, offset int) ([]map[string]interface{}, int64, error)

	// GetGeographicDistribution retrieves geographic distribution of sessions
	GetGeographicDistribution(ctx context.Context) (map[string]int64, error)

	// GetDeviceStats retrieves device statistics
	GetDeviceStats(ctx context.Context) (map[string]int64, error)

	// KickUser forces user logout (kick)
	KickUser(ctx context.Context, userID string) error

	// KickSession forces logout of specific session
	KickSession(ctx context.Context, sessionID string) error

	// LockSession locks a session
	LockSession(ctx context.Context, sessionID string) error

	// UnlockSession unlocks a session
	UnlockSession(ctx context.Context, sessionID string) error

	// DetectSuspiciousActivity detects suspicious user activity
	DetectSuspiciousActivity(ctx context.Context) ([]map[string]interface{}, error)

	// CleanupExpiredSessions removes expired session records
	CleanupExpiredSessions(ctx context.Context) (int64, error)

	// CheckMaxConcurrentSessions checks max concurrent session limit
	CheckMaxConcurrentSessions(ctx context.Context, userID string) (int, error)

	// TerminateOtherSessions terminates other sessions for user (keep-one-active)
	TerminateOtherSessions(ctx context.Context, sessionID string) error

	// UpdateSessionPresence updates session presence status
	UpdateSessionPresence(ctx context.Context, sessionID string, req *SessionPresenceUpdateRequest) error

	// GetSessionPresence retrieves session presence information
	GetSessionPresence(ctx context.Context, sessionID string) (map[string]interface{}, error)

	// GetUserPresence retrieves presence for all user's sessions
	GetUserPresence(ctx context.Context, userID string) ([]map[string]interface{}, error)

	// BroadcastPresenceUpdate broadcasts presence update to connected clients
	BroadcastPresenceUpdate(ctx context.Context, userID string, status string) error

	// GetOnlineUsers retrieves list of online users
	GetOnlineUsers(ctx context.Context) ([]string, error)

	// CheckUserOnlineStatus checks if user is online
	CheckUserOnlineStatus(ctx context.Context, userID string) (bool, error)

	// GetSessionsByDevice retrieves sessions filtered by device type
	GetSessionsByDevice(ctx context.Context, deviceType string, limit, offset int) ([]*models.Session, int64, error)

	// GetSessionsByLocation retrieves sessions from specific location
	GetSessionsByLocation(ctx context.Context, location string, limit, offset int) ([]*models.Session, int64, error)

	// RevokeAllSessionsBeforeDate revokes all sessions before date
	RevokeAllSessionsBeforeDate(ctx context.Context, beforeDate string) (int64, error)

	// GetSessionRiskScore calculates risk score for session
	GetSessionRiskScore(ctx context.Context, sessionID string) (int, error)

	// GetUserSessionRiskScore calculates risk for all user sessions
	GetUserSessionRiskScore(ctx context.Context, userID string) (map[string]interface{}, error)

	// FlagSessionAsRisky flags session as potential security risk
	FlagSessionAsRisky(ctx context.Context, sessionID string, reason string) error

	// GetRiskySessions retrieves flagged risky sessions
	GetRiskySessions(ctx context.Context, limit, offset int) ([]*models.Session, int64, error)

	// SendSessionSecurityAlert sends security alert to user
	SendSessionSecurityAlert(ctx context.Context, sessionID string) error

	// GetSessionSecurityEvents retrieves security-related events
	GetSessionSecurityEvents(ctx context.Context, userID string, limit, offset int) ([]map[string]interface{}, int64, error)
}
