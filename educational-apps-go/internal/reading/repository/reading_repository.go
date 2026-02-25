package repository

import (
	"github.com/architect/educational-apps/internal/common/database"
	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/reading/models"
	"gorm.io/gorm"
)

const (
	WordsMasteredThreshold = 80.0
	WordsInProgressThreshold = 50.0
)

// GetWords retrieves a list of words for practice
func GetWords(limit int) ([]*models.Word, error) {
	var words []*models.Word
	result := database.DB.Limit(limit).Find(&words)
	if result.Error != nil {
		return nil, errors.Internal("failed to fetch words", result.Error.Error())
	}
	return words, nil
}

// CreateWord adds a new word to the database
func CreateWord(word *models.Word) error {
	result := database.DB.Create(word)
	if result.Error != nil {
		return errors.Internal("failed to create word", result.Error.Error())
	}
	return nil
}

// GetWordPerformance retrieves performance data for a specific word
func GetWordPerformance(word string) (*models.WordPerformance, error) {
	var performance models.WordPerformance
	result := database.DB.Where("LOWER(word) = LOWER(?)", word).First(&performance)

	if result.Error != nil {
		if result.Error == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, errors.Internal("failed to fetch word performance", result.Error.Error())
	}

	return &performance, nil
}

// CreateWordPerformance creates a new word performance record
func CreateWordPerformance(perf *models.WordPerformance) error {
	result := database.DB.Create(perf)
	if result.Error != nil {
		return errors.Internal("failed to create word performance", result.Error.Error())
	}
	return nil
}

// UpdateWordPerformance updates word performance after a practice session
func UpdateWordPerformance(word string, isCorrect bool) error {
	perf, err := GetWordPerformance(word)
	if err != nil {
		return err
	}

	if perf == nil {
		// Create new performance record
		newPerf := &models.WordPerformance{
			Word: word,
		}
		if isCorrect {
			newPerf.CorrectCount = 1
		} else {
			newPerf.IncorrectCount = 1
		}
		newPerf.Mastery = calculateMastery(newPerf.CorrectCount, newPerf.IncorrectCount)
		return CreateWordPerformance(newPerf)
	}

	// Update existing performance
	if isCorrect {
		perf.CorrectCount++
	} else {
		perf.IncorrectCount++
	}
	perf.Mastery = calculateMastery(perf.CorrectCount, perf.IncorrectCount)

	result := database.DB.Save(perf)
	if result.Error != nil {
		return errors.Internal("failed to update word performance", result.Error.Error())
	}

	return nil
}

// GetWeakWords retrieves words with low mastery scores
func GetWeakWords(userID uint, limit int) ([]*models.WordPerformance, error) {
	var words []*models.WordPerformance

	result := database.DB.
		Where("mastery < ?", WordsInProgressThreshold).
		Order("mastery ASC").
		Limit(limit).
		Find(&words)

	if result.Error != nil {
		return nil, errors.Internal("failed to fetch weak words", result.Error.Error())
	}

	return words, nil
}

// GetMasteredWords retrieves words with high mastery scores
func GetMasteredWords(userID uint, limit int) ([]*models.WordPerformance, error) {
	var words []*models.WordPerformance

	result := database.DB.
		Where("mastery >= ?", WordsMasteredThreshold).
		Order("mastery DESC").
		Limit(limit).
		Find(&words)

	if result.Error != nil {
		return nil, errors.Internal("failed to fetch mastered words", result.Error.Error())
	}

	return words, nil
}

// calculateMastery calculates mastery percentage based on correct/incorrect counts
func calculateMastery(correct, incorrect int) float64 {
	if correct+incorrect == 0 {
		return 0
	}
	return float64(correct) / float64(correct+incorrect) * 100
}
