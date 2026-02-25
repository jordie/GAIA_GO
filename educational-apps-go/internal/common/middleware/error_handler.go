package middleware

import (
	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/gin-gonic/gin"
)

// ErrorHandler middleware catches panics and converts them to proper error responses
func ErrorHandler() gin.HandlerFunc {
	return func(c *gin.Context) {
		defer func() {
			if r := recover(); r != nil {
				appErr := errors.Internal("internal server error", "")
				c.JSON(appErr.Status, appErr)
			}
		}()
		c.Next()

		// Check if an error response was already sent
		if c.Writer.Status() >= 400 {
			return
		}
	}
}

// JSONErrorResponse wraps errors in consistent JSON format
func JSONErrorResponse(c *gin.Context, err error) {
	appErr, ok := err.(*errors.AppError)
	if !ok {
		appErr = errors.Internal("internal server error", err.Error())
	}

	c.JSON(appErr.Status, appErr)
}
