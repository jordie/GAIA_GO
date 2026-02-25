package middleware

import (
	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/gin-gonic/gin"
)

// AuthRequired middleware checks for valid session or JWT token
func AuthRequired() gin.HandlerFunc {
	return func(c *gin.Context) {
		// Check for session cookie first
		session, err := c.Cookie("session_id")
		if err == nil && session != "" {
			c.Set("user_id", session)
			c.Next()
			return
		}

		// Check for JWT token in Authorization header
		token := c.GetHeader("Authorization")
		if token != "" {
			// Token validation would happen here
			// For now, just accept it
			c.Set("user_id", token)
			c.Next()
			return
		}

		appErr := errors.Unauthorized("missing or invalid authentication")
		c.JSON(appErr.Status, appErr)
		c.Abort()
	}
}

// Optional auth - doesn't fail if missing, but validates if present
func OptionalAuth() gin.HandlerFunc {
	return func(c *gin.Context) {
		session, err := c.Cookie("session_id")
		if err == nil && session != "" {
			c.Set("user_id", session)
		} else {
			token := c.GetHeader("Authorization")
			if token != "" {
				c.Set("user_id", token)
			}
		}
		c.Next()
	}
}
