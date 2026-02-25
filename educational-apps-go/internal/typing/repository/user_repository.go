package repository

import (
	"github.com/architect/educational-apps/internal/common/database"
	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/typing/models"
	"gorm.io/gorm"
)

// CreateUser creates a new user
func CreateUser(username string) (*models.User, error) {
	user := &models.User{
		Username: username,
	}

	result := database.DB.Create(user)
	if result.Error != nil {
		if result.Error == gorm.ErrDuplicatedKey {
			return nil, errors.Conflict("username already exists")
		}
		return nil, errors.Internal("failed to create user", result.Error.Error())
	}

	return user, nil
}

// GetUserByID retrieves a user by ID
func GetUserByID(id uint) (*models.User, error) {
	var user models.User
	result := database.DB.First(&user, id)
	if result.Error != nil {
		if result.Error == gorm.ErrRecordNotFound {
			return nil, errors.NotFound("user")
		}
		return nil, errors.Internal("failed to fetch user", result.Error.Error())
	}
	return &user, nil
}

// GetUserByUsername retrieves a user by username
func GetUserByUsername(username string) (*models.User, error) {
	var user models.User
	result := database.DB.Where("username = ?", username).First(&user)
	if result.Error != nil {
		if result.Error == gorm.ErrRecordNotFound {
			return nil, errors.NotFound("user")
		}
		return nil, errors.Internal("failed to fetch user", result.Error.Error())
	}
	return &user, nil
}

// GetAllUsers retrieves all users
func GetAllUsers() ([]*models.User, error) {
	var users []*models.User
	result := database.DB.Order("username ASC").Find(&users)
	if result.Error != nil {
		return nil, errors.Internal("failed to fetch users", result.Error.Error())
	}
	return users, nil
}

// UpdateUserLastActive updates the last active timestamp
func UpdateUserLastActive(userID uint) error {
	result := database.DB.Model(&models.User{}).
		Where("id = ?", userID).
		Update("last_active", gorm.Expr("CURRENT_TIMESTAMP"))

	if result.Error != nil {
		return errors.Internal("failed to update user", result.Error.Error())
	}

	if result.RowsAffected == 0 {
		return errors.NotFound("user")
	}

	return nil
}

// DeleteUser deletes a user and their associated data
func DeleteUser(userID uint) error {
	// Delete user's results
	if err := database.DB.Where("user_id = ?", userID).Delete(&models.TypingResult{}).Error; err != nil {
		return errors.Internal("failed to delete user results", err.Error())
	}

	// Delete user's stats
	if err := database.DB.Where("user_id = ?", userID).Delete(&models.UserStats{}).Error; err != nil {
		return errors.Internal("failed to delete user stats", err.Error())
	}

	// Delete user
	result := database.DB.Delete(&models.User{}, userID)
	if result.Error != nil {
		return errors.Internal("failed to delete user", result.Error.Error())
	}

	return nil
}
