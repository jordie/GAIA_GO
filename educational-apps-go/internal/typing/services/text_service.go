package services

import (
	"math/rand"
	"strings"

	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/typing/models"
	"github.com/architect/educational-apps/internal/typing/repository"
)

// Text samples for typing practice
var textSamples = map[string][]string{
	"common_words": {
		"the quick brown fox jumps over the lazy dog",
		"pack my box with five dozen liquor jugs",
		"how vexingly quick daft zebras jump",
		"the five boxing wizards jump quickly",
		"sphinx of black quartz judge my vow",
		"two driven jocks help fax my big quiz",
		"five quacking zephyrs jolt my wax bed",
		"the jay pig fox zebra and my wolves quack",
		"a wizard's job is to vex chumps quickly in fog",
		"watch jeopardy alex trebek's fun tv quiz game",
	},
	"programming": {
		"function calculateSum(a, b) { return a + b; }",
		"const array = [1, 2, 3, 4, 5].map(x => x * 2);",
		"if (condition) { doSomething(); } else { doSomethingElse(); }",
		"class MyClass extends BaseClass { constructor() { super(); } }",
		"try { await fetch(url); } catch (error) { console.log(error); }",
		"import React from 'react'; export default App;",
		"def fibonacci(n): return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)",
		"SELECT * FROM users WHERE age > 18 ORDER BY name ASC;",
		"git commit -m 'Initial commit' && git push origin main",
		"docker run -it --rm -p 8080:80 nginx:latest",
	},
	"quotes": {
		"The only way to do great work is to love what you do. - Steve Jobs",
		"Innovation distinguishes between a leader and a follower. - Steve Jobs",
		"Life is what happens when you're busy making other plans. - John Lennon",
		"The future belongs to those who believe in the beauty of their dreams. - Eleanor Roosevelt",
		"It is during our darkest moments that we must focus to see the light. - Aristotle",
		"The best way to predict the future is to create it. - Peter Drucker",
		"Success is not final, failure is not fatal: it is the courage to continue that counts. - Winston Churchill",
		"The only impossible thing is that which you don't attempt. - Unknown",
		"Your time is limited, don't waste it living someone else's life. - Steve Jobs",
		"The greatest glory in living lies not in never falling, but in rising every time we fall. - Nelson Mandela",
	},
	"numbers": {
		"123 456 789 012 345 678 901 234 567 890",
		"3.14159 2.71828 1.41421 1.73205 2.23606",
		"2024 2025 2026 2027 2028 2029 2030 2031",
		"100% 75% 50% 25% 0% -25% -50% -75% -100%",
		"$1,234.56 €987.65 £456.78 ¥123,456 ₹78,901",
		"192.168.1.1 255.255.255.0 127.0.0.1 8.8.8.8",
		"1st 2nd 3rd 4th 5th 6th 7th 8th 9th 10th",
		"1/2 1/3 1/4 2/3 3/4 1/5 2/5 3/5 4/5 1/8",
		"+1 (555) 123-4567 ext. 890 PIN: 1234",
		"10:30 AM 2:45 PM 18:00 23:59 00:00 12:00",
	},
}

// Common words for word mode
var commonWords = []string{
	"the", "be", "to", "of", "and", "a", "in", "that", "have", "I",
	"it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
	"this", "but", "his", "by", "from", "they", "we", "say", "her", "she",
	"or", "an", "will", "my", "one", "all", "would", "there", "their", "what",
	"so", "up", "out", "if", "about", "who", "get", "which", "go", "me",
	"when", "make", "can", "like", "time", "no", "just", "him", "know", "take",
	"people", "into", "year", "your", "good", "some", "could", "them", "see", "other",
	"than", "then", "now", "look", "only", "come", "its", "over", "think", "also",
	"back", "after", "use", "two", "how", "our", "work", "first", "well", "way",
	"even", "new", "want", "because", "any", "these", "give", "day", "most", "us",
}

// GenerateText generates typing practice text
func GenerateText(req models.GetTextRequest) (*models.GetTextResponse, error) {
	var text string
	var wordCount int

	switch req.Type {
	case "words":
		// Generate random words
		if req.WordCount <= 0 {
			req.WordCount = 25
		}
		words := generateRandomWords(req.WordCount)
		text = strings.Join(words, " ")
		wordCount = req.WordCount

	case "time":
		// Generate enough words for timed test (estimate ~3.5 WPM = ~20 chars/word)
		estimatedWords := 200
		words := generateRandomWords(estimatedWords)
		text = strings.Join(words, " ")
		wordCount = estimatedWords

	case "category":
		// Get text from predefined samples
		if req.Category == "" {
			req.Category = "common_words"
		}
		if samples, exists := textSamples[req.Category]; exists {
			text = samples[rand.Intn(len(samples))]
		} else {
			text = textSamples["common_words"][rand.Intn(len(textSamples["common_words"]))]
		}
		wordCount = len(strings.Fields(text))

	default:
		return nil, errors.BadRequest("invalid text type")
	}

	if text == "" {
		return nil, errors.Internal("failed to generate text", "empty text result")
	}

	return &models.GetTextResponse{
		Text:            text,
		WordCount:       wordCount,
		CharacterCount:  len(text),
		Category:        req.Category,
	}, nil
}

// GetUserStats retrieves comprehensive user statistics
func GetUserStats(userID uint) (*models.UserStatsResponse, error) {
	// Validate user exists
	if _, err := GetUser(userID); err != nil {
		return nil, err
	}

	// Get user stats
	userStats, err := repository.GetStatsByUserID(userID)
	if err != nil {
		return nil, err
	}

	// Get recent results
	recentResults, err := repository.GetRecentResults(userID, 10)
	if err != nil {
		return nil, err
	}

	recentResponses := make([]models.TypingResultResponse, len(recentResults))
	for i, r := range recentResults {
		recentResponses[i] = models.TypingResultResponse{
			ID:                  r.ID,
			WPM:                 r.WPM,
			Accuracy:            r.Accuracy,
			TestType:            r.TestType,
			TestDuration:        r.TestDuration,
			TotalCharacters:     r.TotalCharacters,
			CorrectCharacters:   r.CorrectCharacters,
			IncorrectCharacters: r.IncorrectCharacters,
			CreatedAt:           r.CreatedAt,
		}
	}

	// Get best scores by type
	bestScores, err := repository.GetBestScoresByType(userID)
	if err != nil {
		return nil, err
	}

	// Get current user (would come from session in actual implementation)
	user, _ := GetUser(userID)
	username := "Unknown"
	if user != nil {
		username = user.Username
	}

	return &models.UserStatsResponse{
		UserStats:     *userStats,
		RecentResults: recentResponses,
		BestScores:    bestScores,
		CurrentUser:   username,
	}, nil
}

// generateRandomWords generates random words from the common words list
func generateRandomWords(count int) []string {
	words := make([]string, count)
	for i := 0; i < count; i++ {
		words[i] = commonWords[rand.Intn(len(commonWords))]
	}
	return words
}
