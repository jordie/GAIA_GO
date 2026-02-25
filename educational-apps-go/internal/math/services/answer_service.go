package services

import (
	"fmt"
	"time"

	"github.com/architect/educational-apps/internal/math/models"
	"github.com/architect/educational-apps/internal/math/repository"
)

// CheckAnswer validates an answer and updates tracking
func CheckAnswer(userID uint, req models.CheckAnswerRequest) (*models.CheckAnswerResponse, error) {
	isCorrect := req.UserAnswer == req.CorrectAnswer

	// Save to question history
	history := &models.QuestionHistory{
		UserID:        userID,
		Question:      req.Question,
		UserAnswer:    req.UserAnswer,
		CorrectAnswer: req.CorrectAnswer,
		IsCorrect:     isCorrect,
		TimeTaken:     req.TimeTaken,
		FactFamily:    req.FactFamily,
		Mode:          req.Mode,
	}

	if err := repository.SaveQuestionHistory(history); err != nil {
		return nil, err
	}

	// Update mastery tracking
	mastery, err := repository.GetMasteryByFact(userID, req.Question, req.Mode)
	if err != nil {
		return nil, err
	}

	if mastery == nil {
		// Create new mastery record
		mastery = &models.Mastery{
			UserID:        userID,
			Fact:          req.Question,
			Mode:          req.Mode,
			TotalAttempts: 1,
			AverageResponseTime: req.TimeTaken,
			FastestTime:   req.TimeTaken,
			SlowestTime:   req.TimeTaken,
		}
		if isCorrect {
			mastery.CorrectStreak = 1
			mastery.MasteryLevel = 100
		}
		if err := repository.CreateMastery(mastery); err != nil {
			return nil, err
		}
	} else {
		// Update existing mastery
		if isCorrect {
			mastery.CorrectStreak++
		} else {
			mastery.CorrectStreak = 0
			// Track mistake
			mistake := &models.Mistake{
				UserID:        userID,
				Question:      req.Question,
				CorrectAnswer: req.CorrectAnswer,
				UserAnswer:    req.UserAnswer,
				Mode:          req.Mode,
				FactFamily:    req.FactFamily,
				ErrorCount:    1,
				LastError:     time.Now(),
			}
			// Check if mistake exists
			existing, _ := repository.GetMistakes(userID, req.Mode)
			found := false
			for _, m := range existing {
				if m.Question == req.Question {
					repository.UpdateMistake(userID, req.Question, req.Mode)
					found = true
					break
				}
			}
			if !found {
				repository.CreateMistake(mistake)
			}
		}

		mastery.TotalAttempts++
		mastery.LastPracticed = time.Now()

		// Update response time tracking
		mastery.AverageResponseTime = ((mastery.AverageResponseTime * float64(mastery.TotalAttempts-1)) + req.TimeTaken) / float64(mastery.TotalAttempts)
		if req.TimeTaken < mastery.FastestTime {
			mastery.FastestTime = req.TimeTaken
		}
		if req.TimeTaken > mastery.SlowestTime {
			mastery.SlowestTime = req.TimeTaken
		}

		// Calculate new mastery level
		accuracy := float64(mastery.CorrectStreak) / float64(mastery.TotalAttempts)
		speedBonus := 0.0
		if req.TimeTaken < mastery.AverageResponseTime {
			speedBonus = 10
		}
		mastery.MasteryLevel = (accuracy * 80) + (float64(mastery.CorrectStreak) * 4) + speedBonus
		if mastery.MasteryLevel > 100 {
			mastery.MasteryLevel = 100
		}

		if err := repository.UpdateMastery(mastery); err != nil {
			return nil, err
		}
	}

	// Update performance patterns
	updatePerformancePattern(userID, isCorrect, req.TimeTaken)

	explanation := ""
	if !isCorrect {
		explanation = fmt.Sprintf("The correct answer is %s. You answered %s.", req.CorrectAnswer, req.UserAnswer)
	} else {
		explanation = "Correct! Great job!"
	}

	return &models.CheckAnswerResponse{
		IsCorrect:   isCorrect,
		Explanation: explanation,
		NewMastery:  mastery.MasteryLevel,
	}, nil
}

// SaveSession saves a complete practice session
func SaveSession(userID uint, req models.SaveSessionRequest) error {
	// Calculate accuracy
	accuracy := 0.0
	if req.TotalQuestions > 0 {
		accuracy = (float64(req.CorrectAnswers) / float64(req.TotalQuestions)) * 100
	}

	// Calculate average time per question
	avgTime := req.TotalTime / float64(req.TotalQuestions)

	session := &models.SessionResult{
		UserID:         userID,
		Mode:           req.Mode,
		Difficulty:     req.Difficulty,
		TotalQuestions: req.TotalQuestions,
		CorrectAnswers: req.CorrectAnswers,
		TotalTime:      req.TotalTime,
		AverageTime:    avgTime,
		Accuracy:       accuracy,
	}

	return repository.CreateSession(session)
}

// GetUserStats retrieves comprehensive user statistics
func GetUserStats(userID uint) (*models.SessionStatistics, error) {
	stats := &models.SessionStatistics{
		UserID:         userID,
		StrengthAreas:  make(map[string]float64),
		WeakAreas:      make(map[string]float64),
	}

	// Get session statistics
	sessionStats, err := repository.GetSessionStatistics(userID)
	if err == nil && sessionStats != nil {
		if v, ok := sessionStats["total_sessions"]; ok {
			stats.TotalSessions = int(v.(int64))
		}
		if v, ok := sessionStats["average_accuracy"]; ok {
			if val, ok := v.(float64); ok {
				stats.AverageAccuracy = val
			}
		}
		if v, ok := sessionStats["average_time"]; ok {
			if val, ok := v.(float64); ok {
				stats.AverageTime = val
			}
		}
		if v, ok := sessionStats["best_accuracy"]; ok {
			if val, ok := v.(float64); ok {
				stats.BestAccuracy = val
			}
		}
	}

	// Get recent sessions
	sessions, err := repository.GetRecentSessions(userID, 10)
	if err == nil {
		stats.RecentSessions = sessions
	}

	// Get masteries
	masteries, err := repository.GetUserMasteries(userID)
	if err == nil && len(masteries) > 0 {
		// Calculate overall mastery
		totalMastery := 0.0
		for _, m := range masteries {
			totalMastery += m.MasteryLevel
		}
		stats.OverallMastery = totalMastery / float64(len(masteries))

		// Strength areas (mastery > 80)
		for _, m := range masteries {
			if m.MasteryLevel > 80 {
				stats.StrengthAreas[m.Fact] = m.MasteryLevel
			}
		}
	}

	// Get learning profile
	profile, _ := repository.GetLearningProfile(userID)
	if profile != nil {
		stats.LearningProfile = profile
	}

	return stats, nil
}

// updatePerformancePattern updates time-of-day performance patterns
func updatePerformancePattern(userID uint, isCorrect bool, timeTaken float64) {
	now := time.Now()
	hour := now.Hour()
	dayOfWeek := int(now.Weekday())

	accuracy := 0.0
	if isCorrect {
		accuracy = 100
	}

	pattern := &models.PerformancePattern{
		UserID:          userID,
		HourOfDay:       hour,
		DayOfWeek:       dayOfWeek,
		AverageAccuracy: accuracy,
		AverageSpeed:    timeTaken,
		SessionCount:    1,
	}

	repository.UpdatePerformancePattern(pattern)
}
