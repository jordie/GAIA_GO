package typing

import (
	"database/sql"
	"math/rand"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/jgirmay/GAIA_GO/internal/models"
)

// TypingApp manages the typing application
type TypingApp struct {
	db               *sql.DB
	textSamples      map[string][]string
	commonWordsList  []string
}

// NewTypingApp creates a new typing app instance
func NewTypingApp(db *sql.DB) *TypingApp {
	app := &TypingApp{
		db:              db,
		textSamples:    initTextSamples(),
		commonWordsList: initCommonWords(),
	}
	return app
}

// ============================================================================
// TEXT SAMPLES - Different categories for typing practice
// ============================================================================

func initTextSamples() map[string][]string {
	return map[string][]string{
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
		"paragraphs": {
			"In the heart of the bustling city, where skyscrapers touched the clouds and streets hummed with endless activity, there lived a small community of artists who found beauty in the chaos. They gathered each evening in a forgotten courtyard, sharing stories and creating masterpieces that captured the soul of urban life.",
			"Technology has revolutionized the way we communicate, work, and live. From smartphones that connect us instantly to anyone around the world, to artificial intelligence that helps us solve complex problems, we are living in an age of unprecedented innovation. Yet with these advances come new challenges that we must navigate carefully.",
			"The ocean stretched endlessly before her, its waves dancing in the golden light of sunset. She had always found peace by the water, where the rhythmic sound of the tide seemed to wash away the worries of the world. This evening was no different, as she sat on the weathered dock, contemplating the journey that had brought her here.",
			"Learning to code is like learning a new language. At first, the syntax seems foreign and the concepts abstract. But with practice and patience, patterns begin to emerge. Soon, you're not just writing code; you're crafting solutions, building applications, and bringing ideas to life through the power of programming.",
			"The art of cooking is more than just following recipes. It's about understanding flavors, techniques, and the science behind how ingredients interact. A great chef doesn't just cook food; they create experiences, tell stories, and bring people together through the universal language of cuisine.",
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
		"special_characters": {
			"!@#$%^&*()_+-=[]{}|;':\",./<>?",
			"email@example.com user_name@domain.co.uk",
			"https://www.example.com/path?param=value&other=123",
			"C:\\Users\\Name\\Documents\\file.txt",
			"/home/user/documents/project/src/main.py",
			"if (x > 0 && y < 10) { return x * y; }",
			"SELECT * FROM table WHERE column != 'value';",
			"regex: ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
			"#hashtag @mention *bold* _italic_ `code`",
			"Math: x² + y² = r², e = mc², √(a² + b²)",
		},
	}
}

// ============================================================================
// COMMON WORDS - Top 200 most common English words
// ============================================================================

func initCommonWords() []string {
	return []string{
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
		"is", "was", "are", "been", "has", "had", "were", "said", "did", "get",
		"may", "part", "made", "find", "where", "much", "too", "very", "still", "being",
		"going", "why", "before", "never", "here", "more", "out", "do", "like", "just",
		"should", "over", "such", "great", "think", "say", "help", "low", "line", "differ",
		"turn", "cause", "much", "mean", "before", "move", "right", "boy", "old", "too",
		"same", "tell", "does", "set", "three", "want", "air", "well", "also", "play",
		"small", "end", "put", "home", "read", "hand", "port", "large", "spell", "add",
		"land", "here", "must", "big", "high", "such", "follow", "act", "why", "ask",
		"men", "change", "went", "light", "kind", "off", "need", "house", "picture", "try",
		"again", "animal", "point", "mother", "world", "near", "build", "self", "earth", "father",
	}
}

// ============================================================================
// TEXT GENERATION METHODS
// ============================================================================

// GetText returns typing practice text based on test type and parameters
func (app *TypingApp) GetText(testType, category string, wordCount int) string {
	switch testType {
	case "words":
		return app.generateWordText(wordCount)
	case "time":
		return app.generateTimeText(wordCount)
	case "race":
		return app.generateRaceText(wordCount)
	default:
		return app.getRandomTextFromCategory(category)
	}
}

// generateWordText creates text from random common words
func (app *TypingApp) generateWordText(count int) string {
	if count <= 0 {
		count = 25
	}
	words := make([]string, count)
	for i := 0; i < count; i++ {
		words[i] = app.commonWordsList[rand.Intn(len(app.commonWordsList))]
	}
	return strings.Join(words, " ")
}

// generateTimeText creates text for timed typing tests
func (app *TypingApp) generateTimeText(wordCount int) string {
	if wordCount <= 0 {
		wordCount = 200 // ~60 seconds worth of words
	}
	return app.generateWordText(wordCount)
}

// generateRaceText creates text for racing mode
func (app *TypingApp) generateRaceText(wordCount int) string {
	if wordCount <= 0 {
		wordCount = 30 // Standard race length
	}
	return app.generateWordText(wordCount)
}

// getRandomTextFromCategory returns random text from a category
func (app *TypingApp) getRandomTextFromCategory(category string) string {
	texts, exists := app.textSamples[category]
	if !exists || len(texts) == 0 {
		texts = app.textSamples["common_words"]
	}
	return texts[rand.Intn(len(texts))]
}

// ============================================================================
// RESULT CALCULATION METHODS
// ============================================================================

// CalculateWPM calculates words per minute from typing metrics
func CalculateWPM(totalCharacters int, timeTakenSeconds float64) int {
	if timeTakenSeconds == 0 {
		return 0
	}
	// Standard: 5 characters = 1 word
	words := float64(totalCharacters) / 5.0
	minutes := timeTakenSeconds / 60.0
	return int(words / minutes)
}

// CalculateAccuracy calculates accuracy percentage
func CalculateAccuracy(correctCharacters, totalCharacters int) float64 {
	if totalCharacters == 0 {
		return 0
	}
	return float64(correctCharacters*100) / float64(totalCharacters)
}

// CalculateRawWPM calculates WPM before accuracy adjustment
func CalculateRawWPM(totalCharacters int, timeTakenSeconds float64) int {
	return CalculateWPM(totalCharacters, timeTakenSeconds)
}

// ============================================================================
// RACING SYSTEM
// ============================================================================

// AIOpponent represents an AI opponent in a race
type AIOpponent struct {
	ID       string `json:"id"`
	Name     string `json:"name"`
	WPM      int    `json:"wpm"`
	Accuracy int    `json:"accuracy"`
	Car      string `json:"car"`
	Progress int    `json:"progress"`
}

// RaceConfig holds configuration for race difficulty
type RaceConfig struct {
	WPMRange      [2]int
	AccuracyRange [2]int
	Names         []string
}

// RaceConfigs defines difficulty-based race configurations
var RaceConfigs = map[string]RaceConfig{
	"easy": {
		WPMRange:      [2]int{20, 35},
		AccuracyRange: [2]int{90, 95},
		Names:         []string{"Rookie", "Beginner", "Learner", "Newbie"},
	},
	"medium": {
		WPMRange:      [2]int{40, 60},
		AccuracyRange: [2]int{93, 97},
		Names:         []string{"SpeedBot", "TypeMaster", "SwiftKeys", "QuickType"},
	},
	"hard": {
		WPMRange:      [2]int{70, 100},
		AccuracyRange: [2]int{95, 99},
		Names:         []string{"Nitro", "Lightning", "ProTyper", "Thunder"},
	},
}

var carEmojis = []string{"🚗", "🚙", "🚕", "🏎️"}

// GenerateRaceOpponents creates AI opponents for a race
func (app *TypingApp) GenerateRaceOpponents(difficulty string, wordCount int) (string, []AIOpponent) {
	config, exists := RaceConfigs[difficulty]
	if !exists {
		config = RaceConfigs["medium"]
	}

	raceText := app.generateRaceText(wordCount)
	usedNames := make(map[string]bool)
	opponents := make([]AIOpponent, 3)

	for i := 0; i < 3; i++ {
		// Pick unique name
		var name string
		for {
			name = config.Names[rand.Intn(len(config.Names))]
			if !usedNames[name] {
				usedNames[name] = true
				break
			}
		}

		opponents[i] = AIOpponent{
			ID:       "ai_" + string(rune(i+1+'0')),
			Name:     name,
			WPM:      config.WPMRange[0] + rand.Intn(config.WPMRange[1]-config.WPMRange[0]),
			Accuracy: config.AccuracyRange[0] + rand.Intn(config.AccuracyRange[1]-config.AccuracyRange[0]),
			Car:      carEmojis[i%len(carEmojis)],
			Progress: 0,
		}
	}

	return raceText, opponents
}

// ============================================================================
// XP CALCULATION
// ============================================================================

// CalculateRaceXP calculates XP earned from a race
func CalculateRaceXP(wpm int, accuracy float64, placement int, difficulty string) int {
	baseXP := 10
	placementBonus := map[int]int{
		1: 50,
		2: 30,
		3: 15,
		4: 0,
	}

	accuracy_bonus := 0
	if accuracy >= 100 {
		accuracy_bonus = 25
	} else if accuracy >= 95 {
		accuracy_bonus = 15
	}

	speed_bonus := 0
	if wpm >= 60 {
		speed_bonus = 20
	} else if wpm >= 40 {
		speed_bonus = 10
	}

	bonus := placementBonus[placement]
	if bonus == 0 && placement > 4 {
		bonus = 0
	}

	multiplier := 1.0
	switch difficulty {
	case "easy":
		multiplier = 1.0
	case "medium":
		multiplier = 1.2
	case "hard":
		multiplier = 1.5
	}

	xp := float64(baseXP+bonus+accuracy_bonus+speed_bonus) * multiplier
	return int(xp)
}

// ============================================================================
// CAR PROGRESSION
// ============================================================================

// GetCarForXP returns emoji car based on XP earned
func GetCarForXP(totalXP int) string {
	switch {
	case totalXP >= 1000:
		return "🚀"
	case totalXP >= 500:
		return "🏎️"
	case totalXP >= 250:
		return "🚕"
	case totalXP >= 100:
		return "🚙"
	default:
		return "🚗"
	}
}

// InitDB initializes the typing database tables
func (app *TypingApp) InitDB() error {
	// Tables are created by main migration, but we could add app-specific initialization here
	_, err := app.db.Exec(`
		CREATE TABLE IF NOT EXISTS typing_results (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			user_id INTEGER,
			wpm INTEGER NOT NULL,
			raw_wpm INTEGER,
			accuracy REAL NOT NULL,
			test_type TEXT,
			test_mode TEXT,
			test_duration INTEGER,
			total_characters INTEGER,
			correct_characters INTEGER,
			incorrect_characters INTEGER,
			errors INTEGER,
			time_taken REAL,
			text_snippet TEXT,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			FOREIGN KEY (user_id) REFERENCES users(id)
		)
	`)
	return err
}

// ============================================================================
// APP INTERFACE IMPLEMENTATION
// ============================================================================

// GetName returns the app identifier
func (app *TypingApp) GetName() string {
	return "typing"
}

// GetDisplayName returns the human-readable app name
func (app *TypingApp) GetDisplayName() string {
	return "Typing Master"
}

// GetDescription returns app description
func (app *TypingApp) GetDescription() string {
	return "Test and improve your typing speed and accuracy"
}

// GetVersion returns app version
func (app *TypingApp) GetVersion() string {
	return "2.0.0"
}

// RegisterRoutes registers all HTTP routes for the typing app
// Routes are actually registered by handlers.go's RegisterHandlers function
func (app *TypingApp) RegisterRoutes(router *gin.RouterGroup) {
	// Stub implementation - actual routes registered by handlers.RegisterHandlers
}

// GetUserStats returns typing-specific stats for a user
func (app *TypingApp) GetUserStats(userID int64) (map[string]interface{}, error) {
	var stats models.TypingStats
	err := app.db.QueryRow(
		`SELECT id, user_id, total_tests, average_wpm, average_accuracy, best_wpm, total_time_typed
		 FROM typing_stats WHERE user_id = ?`,
		userID,
	).Scan(&stats.ID, &stats.UserID, &stats.TotalSessions, &stats.AverageWPM, &stats.AverageAccuracy, &stats.BestWPM, &stats.TotalTime)

	if err != nil && err != sql.ErrNoRows {
		return nil, err
	}

	return map[string]interface{}{
		"total_tests":     stats.TotalSessions,
		"average_wpm":     stats.AverageWPM,
		"average_accuracy": stats.AverageAccuracy,
		"best_wpm":        stats.BestWPM,
		"total_time":      stats.TotalTime,
	}, nil
}

// GetLeaderboard returns top typists
func (app *TypingApp) GetLeaderboard(limit int) ([]map[string]interface{}, error) {
	if limit <= 0 || limit > 100 {
		limit = 10
	}

	rows, err := app.db.Query(`
		SELECT u.username, s.best_wpm, s.average_accuracy, s.total_tests
		FROM typing_stats s
		JOIN users u ON s.user_id = u.id
		WHERE s.total_tests > 0
		ORDER BY s.best_wpm DESC
		LIMIT ?
	`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var results []map[string]interface{}
	for rows.Next() {
		var username string
		var bestWPM int
		var avgAccuracy float64
		var totalTests int

		if err := rows.Scan(&username, &bestWPM, &avgAccuracy, &totalTests); err != nil {
			continue
		}

		results = append(results, map[string]interface{}{
			"username":         username,
			"best_wpm":         bestWPM,
			"average_accuracy": avgAccuracy,
			"total_tests":      totalTests,
		})
	}

	return results, nil
}
