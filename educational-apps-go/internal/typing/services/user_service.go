package services

import (
	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/common/validation"
	"github.com/architect/educational-apps/internal/typing/models"
	"github.com/architect/educational-apps/internal/typing/repository"
)

// CreateUser creates a new user with validation
func CreateUser(username string) (*models.User, error) {
	// Validate username
	if err := validation.ValidateStringRange(username, 2, 20); err != nil {
		return nil, errors.BadRequest("username must be between 2 and 20 characters")
	}

	// Create user
	user, err := repository.CreateUser(username)
	if err != nil {
		return nil, err
	}

	// Initialize user stats
	stats := &models.UserStats{
		UserID:     user.ID,
		TotalTests: 0,
	}
	if err := repository.CreateStats(stats); err != nil {
		return nil, err
	}

	return user, nil
}

// GetUser retrieves a user by ID
func GetUser(userID uint) (*models.User, error) {
	if userID == 0 {
		return nil, errors.BadRequest("invalid user ID")
	}
	return repository.GetUserByID(userID)
}

// GetUsers retrieves all users
func GetUsers() ([]*models.User, error) {
	return repository.GetAllUsers()
}

// SwitchUser validates and switches to a different user
func SwitchUser(userID uint) (*models.User, error) {
	if userID == 0 {
		return nil, errors.BadRequest("invalid user ID")
	}

	user, err := repository.GetUserByID(userID)
	if err != nil {
		return nil, err
	}

	// Update last active
	if err := repository.UpdateUserLastActive(userID); err != nil {
		// Log error but don't fail the switch
	}

	return user, nil
}

// DeleteUser removes a user and their data
func DeleteUser(userID uint) error {
	if userID == 0 {
		return errors.BadRequest("invalid user ID")
	}
	return repository.DeleteUser(userID)
}
