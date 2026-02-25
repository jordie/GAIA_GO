package handlers

import (
	"strconv"

	"github.com/architect/educational-apps/internal/common/middleware"
	"github.com/architect/educational-apps/internal/piano/models"
	"github.com/architect/educational-apps/internal/piano/services"
	"github.com/gin-gonic/gin"
)

// GetExercises retrieves all exercises
func GetExercises(c *gin.Context) {
	// Query parameters
	difficulty := c.Query("difficulty")
	page := c.DefaultQuery("page", "1")
	pageSize := c.DefaultQuery("page_size", "20")

	// Parse parameters
	pageNum, err := strconv.Atoi(page)
	if err != nil || pageNum < 1 {
		pageNum = 1
	}

	pageSizeNum, err := strconv.Atoi(pageSize)
	if err != nil || pageSizeNum < 1 || pageSizeNum > 100 {
		pageSizeNum = 20
	}

	var difficultyLevel *int
	if difficulty != "" {
		d, err := strconv.Atoi(difficulty)
		if err == nil && d >= 1 && d <= 5 {
			difficultyLevel = &d
		}
	}

	result, err := services.GetExercises(difficultyLevel, pageNum, pageSizeNum)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, result)
}

// GetExerciseByID retrieves a specific exercise
func GetExerciseByID(c *gin.Context) {
	id, err := strconv.ParseUint(c.Param("id"), 10, 32)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	exercise, err := services.GetExerciseByID(uint(id))
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, exercise)
}

// CreateExercise creates a new exercise
func CreateExercise(c *gin.Context) {
	var req models.CreateExerciseRequest

	if err := c.ShouldBindJSON(&req); err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	exercise, err := services.CreateExercise(req)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(201, exercise)
}

// UpdateExercise updates an existing exercise
func UpdateExercise(c *gin.Context) {
	id, err := strconv.ParseUint(c.Param("id"), 10, 32)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	var req models.CreateExerciseRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	exercise, err := services.UpdateExercise(uint(id), req)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, exercise)
}

// DeleteExercise deletes an exercise
func DeleteExercise(c *gin.Context) {
	id, err := strconv.ParseUint(c.Param("id"), 10, 32)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	if err := services.DeleteExercise(uint(id)); err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(204, nil)
}
