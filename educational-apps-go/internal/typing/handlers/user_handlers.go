package handlers

import (
	"strconv"

	"github.com/architect/educational-apps/internal/common/middleware"
	"github.com/architect/educational-apps/internal/typing/models"
	"github.com/architect/educational-apps/internal/typing/services"
	"github.com/gin-gonic/gin"
)

// CreateUser creates a new user
func CreateUser(c *gin.Context) {
	var req models.CreateUserRequest

	if err := c.ShouldBindJSON(&req); err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	user, err := services.CreateUser(req.Username)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(201, gin.H{
		"success":  true,
		"user_id":  user.ID,
		"username": user.Username,
	})
}

// GetCurrentUser gets the current session user
func GetCurrentUser(c *gin.Context) {
	userIDStr, exists := c.Get("user_id")
	if !exists {
		// Return guest user
		c.JSON(200, gin.H{
			"user_id":  nil,
			"username": "Guest",
		})
		return
	}

	userID, err := strconv.ParseUint(userIDStr.(string), 10, 32)
	if err != nil {
		c.JSON(200, gin.H{
			"user_id":  nil,
			"username": "Guest",
		})
		return
	}

	user, err := services.GetUser(uint(userID))
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, gin.H{
		"user_id":  user.ID,
		"username": user.Username,
	})
}

// GetUsers gets all users
func GetUsers(c *gin.Context) {
	users, err := services.GetUsers()
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	response := make([]models.UserResponse, len(users))
	for i, u := range users {
		response[i] = models.UserResponse{
			ID:         u.ID,
			Username:   u.Username,
			CreatedAt:  u.CreatedAt,
			LastActive: u.LastActive,
		}
	}

	c.JSON(200, response)
}

// SwitchUser switches to a different user
func SwitchUser(c *gin.Context) {
	var req models.SwitchUserRequest

	if err := c.ShouldBindJSON(&req); err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	user, err := services.SwitchUser(req.UserID)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	// Update session
	c.Set("user_id", user.ID)

	c.JSON(200, gin.H{
		"success":  true,
		"username": user.Username,
	})
}

// DeleteUser deletes a user (admin only)
func DeleteUser(c *gin.Context) {
	userID, err := strconv.ParseUint(c.Param("id"), 10, 32)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	if err := services.DeleteUser(uint(userID)); err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, gin.H{
		"success": true,
		"message": "user deleted successfully",
	})
}
