package main

import (
	"database/sql"
	"flag"
	"fmt"
	"log"
	"math"
	"os"
	"time"

	"github.com/google/uuid"
	_ "github.com/lib/pq"
	_ "github.com/mattn/go-sqlite3"
)

type Config struct {
	DBType   string // "sqlite" or "postgres"
	DBPath   string // For SQLite
	ConnStr  string // For PostgreSQL
	NumUsers int
}

var config Config

func init() {
	flag.StringVar(&config.DBType, "db-type", "sqlite", "Database type: sqlite or postgres")
	flag.StringVar(&config.DBPath, "output", "./data/educational_apps.db", "SQLite database path")
	flag.StringVar(&config.ConnStr, "conn", "postgres://app_user:secure_password_123@localhost:5432/educational_apps_prod", "PostgreSQL connection string")
	flag.IntVar(&config.NumUsers, "users", 100, "Number of users to generate")
}

func main() {
	flag.Parse()

	db, err := connectDB()
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer db.Close()

	log.Println("🌱 Starting data seeding...")

	// Create users and sessions
	userIDs, err := seedUsers(db, config.NumUsers)
	if err != nil {
		log.Fatalf("Failed to seed users: %v", err)
	}
	log.Printf("✅ Created %d users", len(userIDs))

	// Create reading data
	lessonIDs, err := seedReadingLessons(db)
	if err != nil {
		log.Fatalf("Failed to seed reading lessons: %v", err)
	}
	err = seedReadingWordMastery(db, userIDs)
	if err != nil {
		log.Fatalf("Failed to seed reading word mastery: %v", err)
	}
	log.Printf("✅ Created %d reading lessons and word mastery records", lessonIDs, 500)

	// Create math data
	problemIDs, err := seedMathProblems(db, 1000)
	if err != nil {
		log.Fatalf("Failed to seed math problems: %v", err)
	}
	err = seedMathAttempts(db, userIDs, problemIDs)
	if err != nil {
		log.Fatalf("Failed to seed math attempts: %v", err)
	}
	log.Printf("✅ Created %d math problems and attempts", len(problemIDs))

	// Create piano data
	exerciseIDs, err := seedPianoExercises(db, 200)
	if err != nil {
		log.Fatalf("Failed to seed piano exercises: %v", err)
	}
	err = seedPianoAttempts(db, userIDs, exerciseIDs)
	if err != nil {
		log.Fatalf("Failed to seed piano attempts: %v", err)
	}
	log.Printf("✅ Created %d piano exercises and attempts", len(exerciseIDs))

	// Create typing data
	typingExerciseIDs, err := seedTypingExercises(db, 300)
	if err != nil {
		log.Fatalf("Failed to seed typing exercises: %v", err)
	}
	err = seedTypingAttempts(db, userIDs, typingExerciseIDs)
	if err != nil {
		log.Fatalf("Failed to seed typing attempts: %v", err)
	}
	log.Printf("✅ Created %d typing exercises and attempts", len(typingExerciseIDs))

	// Create comprehension data
	passageIDs, err := seedComprehensionPassages(db, 150)
	if err != nil {
		log.Fatalf("Failed to seed comprehension passages: %v", err)
	}
	err = seedComprehensionAnswers(db, userIDs, passageIDs)
	if err != nil {
		log.Fatalf("Failed to seed comprehension answers: %v", err)
	}
	log.Printf("✅ Created %d comprehension passages and answers", len(passageIDs))

	log.Println("\n🎉 Data seeding complete!")
	logStatistics(db)
}

func connectDB() (*sql.DB, error) {
	var db *sql.DB
	var err error

	if config.DBType == "sqlite" {
		os.MkdirAll("./data", 0755)
		db, err = sql.Open("sqlite3", config.DBPath)
	} else if config.DBType == "postgres" {
		db, err = sql.Open("postgres", config.ConnStr)
	} else {
		return nil, fmt.Errorf("unsupported database type: %s", config.DBType)
	}

	if err != nil {
		return nil, err
	}

	if err := db.Ping(); err != nil {
		return nil, err
	}

	return db, nil
}

func seedUsers(db *sql.DB, count int) ([]int64, error) {
	var userIDs []int64
	now := time.Now()

	for i := 1; i <= count; i++ {
		username := fmt.Sprintf("user_%d", i)
		email := fmt.Sprintf("user%d@example.com", i)
		displayName := fmt.Sprintf("User %d", i)
		passwordHash := fmt.Sprintf("hashed_password_%d", i)

		var userID int64
		err := db.QueryRow(
			`INSERT INTO users (username, email, password_hash, display_name, created_at, updated_at, last_login)
			 VALUES (?, ?, ?, ?, ?, ?, ?)
			 RETURNING id`,
			username, email, passwordHash, displayName, now, now, now,
		).Scan(&userID)

		if err != nil {
			return nil, err
		}

		// Create session for user
		sessionToken := uuid.New().String()
		expiresAt := now.Add(24 * time.Hour)

		_, err = db.Exec(
			`INSERT INTO sessions (user_id, session_token, expires_at, created_at, last_activity)
			 VALUES (?, ?, ?, ?, ?)`,
			userID, sessionToken, expiresAt, now, now,
		)

		if err != nil {
			return nil, err
		}

		userIDs = append(userIDs, userID)
	}

	return userIDs, nil
}

func seedReadingLessons(db *sql.DB) ([]int64, error) {
	var lessonIDs []int64
	now := time.Now()

	lessons := []struct {
		title       string
		description string
		level       int
		content     string
	}{
		{"The Lion and the Mouse", "A classic fable about kindness", 1, "Once upon a time, a lion was sleeping..."},
		{"The Tortoise and the Hare", "A tale about persistence", 1, "In a forest lived a tortoise and a hare..."},
		{"The Boy Who Cried Wolf", "A story about honesty", 1, "There was a shepherd boy in the valley..."},
		{"Cinderella", "A fairy tale of magic and kindness", 2, "Once upon a time, there lived a girl named Cinderella..."},
		{"Snow White", "A story of true love and magic", 2, "In a kingdom far away lived a princess..."},
		{"The Little Red Riding Hood", "A cautionary tale", 2, "A young girl wore a red riding hood..."},
		{"Jack and the Beanstalk", "An adventure story", 3, "Once there lived a poor boy named Jack..."},
		{"The Sleeping Beauty", "A tale of a curse and true love", 3, "In an ancient kingdom, a princess was born..."},
		{"The Three Little Pigs", "A story about hard work", 1, "Once upon a time, three pigs lived with their mother..."},
		{"Hansel and Gretel", "An adventure into the forest", 3, "In a small cottage lived two poor children..."},
	}

	for _, lesson := range lessons {
		var lessonID int64
		err := db.QueryRow(
			`INSERT INTO reading_lessons (title, description, difficulty_level, content, created_at, updated_at)
			 VALUES (?, ?, ?, ?, ?, ?)
			 RETURNING id`,
			lesson.title, lesson.description, lesson.level, lesson.content, now, now,
		).Scan(&lessonID)

		if err != nil {
			return nil, err
		}

		lessonIDs = append(lessonIDs, lessonID)
	}

	return lessonIDs, nil
}

func seedReadingWordMastery(db *sql.DB, userIDs []int64) error {
	words := []string{
		"elephant", "adventure", "perseverance", "kingdom", "magic",
		"courage", "wisdom", "friendship", "mystery", "discovery",
		"challenge", "triumph", "journey", "ancient", "forest",
		"castle", "dragon", "enchanted", "quest", "legend",
	}

	now := time.Now()

	for _, userID := range userIDs {
		for i, word := range words {
			proficiency := int64((i * 10) % 100)
			_, err := db.Exec(
				`INSERT INTO reading_word_mastery (user_id, word, proficiency_level, times_practiced, last_practiced, created_at, updated_at)
				 VALUES (?, ?, ?, ?, ?, ?, ?)`,
				userID, word, proficiency, i+1, now.Add(-time.Duration(i)*time.Hour), now, now,
			)

			if err != nil {
				return err
			}
		}
	}

	return nil
}

func seedMathProblems(db *sql.DB, count int) ([]int64, error) {
	var problemIDs []int64
	now := time.Now()
	operators := []string{"+", "-", "*", "/"}

	for i := 0; i < count; i++ {
		difficulty := (i % 5) + 1
		operand1 := int32((i % 100) + 1)
		operand2 := int32(((i * 7) % 50) + 1)
		operator := operators[i%len(operators)]
		var answer int32

		switch operator {
		case "+":
			answer = operand1 + operand2
		case "-":
			answer = operand1 - operand2
		case "*":
			answer = operand1 * operand2
		case "/":
			if operand2 == 0 {
				operand2 = 1
			}
			answer = operand1 / operand2
		}

		var problemID int64
		err := db.QueryRow(
			`INSERT INTO math_problems (difficulty_level, problem_type, operand1, operand2, operator, correct_answer, created_at)
			 VALUES (?, ?, ?, ?, ?, ?, ?)
			 RETURNING id`,
			difficulty, "arithmetic", operand1, operand2, operator, answer, now,
		).Scan(&problemID)

		if err != nil {
			return nil, err
		}

		problemIDs = append(problemIDs, problemID)
	}

	return problemIDs, nil
}

func seedMathAttempts(db *sql.DB, userIDs []int64, problemIDs []int64) error {
	now := time.Now()

	for i, userID := range userIDs {
		// Each user attempts 50 problems
		for j := 0; j < 50 && (i*50+j) < len(problemIDs); j++ {
			problemID := problemIDs[i*50+j]
			userAnswer := int32((i * 7 + j) % 1000)
			isCorrect := (j % 3) == 0 // 33% accuracy
			responseTime := int32((j * 100) + 500)

			_, err := db.Exec(
				`INSERT INTO math_attempts (user_id, problem_id, user_answer, is_correct, response_time_ms, attempted_at)
				 VALUES (?, ?, ?, ?, ?, ?)`,
				userID, problemID, userAnswer, isCorrect, responseTime, now.Add(-time.Duration(j)*time.Minute),
			)

			if err != nil {
				return err
			}
		}

		// Update math progress
		totalSolved := int32(50)
		accuracy := int64(33)
		_, err := db.Exec(
			`INSERT INTO math_progress (user_id, current_difficulty_level, total_problems_solved, accuracy_percentage, updated_at)
			 VALUES (?, ?, ?, ?, ?)
			 ON CONFLICT(user_id) DO UPDATE SET
			 total_problems_solved = ?, accuracy_percentage = ?, updated_at = ?`,
			userID, 2, totalSolved, accuracy, now,
			totalSolved, accuracy, now,
		)

		if err != nil {
			return err
		}
	}

	return nil
}

func seedPianoExercises(db *sql.DB, count int) ([]int64, error) {
	var exerciseIDs []int64
	now := time.Now()

	notes := []string{"C", "D", "E", "F", "G", "A", "B"}

	for i := 0; i < count; i++ {
		difficulty := (i % 5) + 1
		title := fmt.Sprintf("Piano Exercise %d", i+1)
		description := fmt.Sprintf("Exercise level %d", difficulty)

		// Generate a sequence of notes
		noteSeq := ""
		for j := 0; j < (difficulty + 2); j++ {
			noteSeq += notes[(i*7+j)%len(notes)] + " "
		}

		var exerciseID int64
		err := db.QueryRow(
			`INSERT INTO piano_exercises (title, description, difficulty_level, notes_sequence, created_at)
			 VALUES (?, ?, ?, ?, ?)
			 RETURNING id`,
			title, description, difficulty, noteSeq, now,
		).Scan(&exerciseID)

		if err != nil {
			return nil, err
		}

		exerciseIDs = append(exerciseIDs, exerciseID)
	}

	return exerciseIDs, nil
}

func seedPianoAttempts(db *sql.DB, userIDs []int64, exerciseIDs []int64) error {
	now := time.Now()
	notes := []string{"C", "D", "E", "F", "G", "A", "B"}

	for i, userID := range userIDs {
		// Each user attempts 20 exercises
		for j := 0; j < 20 && (i*20+j) < len(exerciseIDs); j++ {
			exerciseID := exerciseIDs[i*20+j]

			// Generate notes played
			notesPlayed := ""
			for k := 0; k < (j + 2); k++ {
				notesPlayed += notes[(i*7+j+k)%len(notes)] + " "
			}

			isCorrect := (j % 2) == 0
			accuracy := float64(75 + (j * 2))
			responseTime := int32((j * 200) + 1000)

			_, err := db.Exec(
				`INSERT INTO piano_attempts (user_id, exercise_id, notes_played, is_correct, accuracy_percentage, response_time_ms, attempted_at)
				 VALUES (?, ?, ?, ?, ?, ?, ?)`,
				userID, exerciseID, notesPlayed, isCorrect, accuracy, responseTime, now.Add(-time.Duration(j)*time.Minute),
			)

			if err != nil {
				return err
			}
		}
	}

	return nil
}

func seedTypingExercises(db *sql.DB, count int) ([]int64, error) {
	var exerciseIDs []int64
	now := time.Now()

	texts := []string{
		"The quick brown fox jumps over the lazy dog.",
		"Pack my box with five dozen liquor jugs.",
		"How vexingly quick daft zebras jump!",
		"The five boxing wizards jump quickly.",
		"Sphinx of black quartz, judge my vow.",
		"The jay, pig, fox, zebra and my wolves quack!",
		"Waltz, nymph, for quick jigs vex Bud.",
	}

	for i := 0; i < count; i++ {
		difficulty := (i % 5) + 1
		title := fmt.Sprintf("Typing Exercise %d", i+1)
		text := texts[i%len(texts)]

		var exerciseID int64
		err := db.QueryRow(
			`INSERT INTO typing_exercises (title, text_content, difficulty_level, created_at)
			 VALUES (?, ?, ?, ?)
			 RETURNING id`,
			title, text, difficulty, now,
		).Scan(&exerciseID)

		if err != nil {
			return nil, err
		}

		exerciseIDs = append(exerciseIDs, exerciseID)
	}

	return exerciseIDs, nil
}

func seedTypingAttempts(db *sql.DB, userIDs []int64, exerciseIDs []int64) error {
	now := time.Now()

	for i, userID := range userIDs {
		// Each user attempts 30 exercises
		for j := 0; j < 30 && (i*30+j) < len(exerciseIDs); j++ {
			exerciseID := exerciseIDs[i*30+j]
			textTyped := "The quick brown fox jumps over the lazy dog."
			accuracy := float64(70 + (j % 30))
			wpm := int32(40 + (j % 60))
			duration := int32(30 + (j % 20))

			_, err := db.Exec(
				`INSERT INTO typing_attempts (user_id, exercise_id, text_typed, accuracy_percentage, wpm, duration_seconds, attempted_at)
				 VALUES (?, ?, ?, ?, ?, ?, ?)`,
				userID, exerciseID, textTyped, accuracy, wpm, duration, now.Add(-time.Duration(j)*time.Minute),
			)

			if err != nil {
				return err
			}
		}

		// Update typing progress
		avgWPM := int32(50 + (i % 30))
		avgAccuracy := float64(75 + math.Mod(float64(i*3), 20))
		_, err := db.Exec(
			`INSERT INTO typing_progress (user_id, average_wpm, average_accuracy, total_exercises_completed, updated_at)
			 VALUES (?, ?, ?, ?, ?)
			 ON CONFLICT(user_id) DO UPDATE SET
			 average_wpm = ?, average_accuracy = ?, total_exercises_completed = ?, updated_at = ?`,
			userID, avgWPM, avgAccuracy, 30, now,
			avgWPM, avgAccuracy, 30, now,
		)

		if err != nil {
			return err
		}
	}

	return nil
}

func seedComprehensionPassages(db *sql.DB, count int) ([]int64, error) {
	var passageIDs []int64
	now := time.Now()

	passages := []struct {
		title    string
		content  string
		level    int
		question string
		answer   string
	}{
		{
			"The Solar System",
			"Our solar system consists of the Sun and eight planets. The planets are Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, and Neptune.",
			1,
			"How many planets are in our solar system?",
			"Eight",
		},
		{
			"Ancient Egypt",
			"Ancient Egypt was a civilization that thrived along the Nile River. The Egyptians built pyramids, developed writing, and created a complex society.",
			2,
			"What river was central to Ancient Egypt?",
			"The Nile River",
		},
		{
			"The Amazon Rainforest",
			"The Amazon rainforest is the largest tropical rainforest in the world. It covers an area of about 5.5 million square kilometers and is home to millions of species.",
			2,
			"Where is the Amazon rainforest located?",
			"In South America",
		},
		{
			"Technology and Society",
			"Technology has revolutionized modern society. From communication to transportation, technology has made our lives more connected and efficient.",
			3,
			"How has technology affected communication?",
			"Made it more connected",
		},
		{
			"Climate Change",
			"Climate change is a pressing global issue caused primarily by human activities such as burning fossil fuels. It leads to rising temperatures and extreme weather.",
			3,
			"What is a primary cause of climate change?",
			"Burning fossil fuels",
		},
	}

	for i := 0; i < count; i++ {
		passage := passages[i%len(passages)]
		var passageID int64

		err := db.QueryRow(
			`INSERT INTO comprehension_passages (title, content, difficulty_level, created_at)
			 VALUES (?, ?, ?, ?)
			 RETURNING id`,
			passage.title, passage.content, passage.level, now,
		).Scan(&passageID)

		if err != nil {
			return nil, err
		}

		// Add questions to passage
		_, err = db.Exec(
			`INSERT INTO comprehension_questions (passage_id, question_text, question_type, correct_answer, created_at)
			 VALUES (?, ?, ?, ?, ?)`,
			passageID, passage.question, "multiple_choice", passage.answer, now,
		)

		if err != nil {
			return nil, err
		}

		passageIDs = append(passageIDs, passageID)
	}

	return passageIDs, nil
}

func seedComprehensionAnswers(db *sql.DB, userIDs []int64, passageIDs []int64) error {
	now := time.Now()

	for i, userID := range userIDs {
		// Each user answers 25 questions
		for j := 0; j < 25 && (i*25+j) < len(passageIDs); j++ {
			passageID := passageIDs[i*25+j]

			// Get questions for this passage
			var questionID int64
			err := db.QueryRow(
				`SELECT id FROM comprehension_questions WHERE passage_id = ? LIMIT 1`,
				passageID,
			).Scan(&questionID)

			if err != nil && err != sql.ErrNoRows {
				return err
			}

			if err == sql.ErrNoRows {
				continue
			}

			userAnswer := "Correct Answer"
			isCorrect := (j % 2) == 0

			_, err = db.Exec(
				`INSERT INTO comprehension_answers (user_id, question_id, user_answer, is_correct, answered_at)
				 VALUES (?, ?, ?, ?, ?)`,
				userID, questionID, userAnswer, isCorrect, now.Add(-time.Duration(j)*time.Minute),
			)

			if err != nil {
				return err
			}
		}
	}

	return nil
}

func logStatistics(db *sql.DB) {
	fmt.Println("\n📊 Database Statistics:")
	fmt.Println("========================")

	queries := map[string]string{
		"Users":                    "SELECT COUNT(*) FROM users",
		"Sessions":                 "SELECT COUNT(*) FROM sessions",
		"Reading Lessons":          "SELECT COUNT(*) FROM reading_lessons",
		"Word Mastery Records":     "SELECT COUNT(*) FROM reading_word_mastery",
		"Math Problems":            "SELECT COUNT(*) FROM math_problems",
		"Math Attempts":            "SELECT COUNT(*) FROM math_attempts",
		"Piano Exercises":          "SELECT COUNT(*) FROM piano_exercises",
		"Piano Attempts":           "SELECT COUNT(*) FROM piano_attempts",
		"Typing Exercises":         "SELECT COUNT(*) FROM typing_exercises",
		"Typing Attempts":          "SELECT COUNT(*) FROM typing_attempts",
		"Comprehension Passages":   "SELECT COUNT(*) FROM comprehension_passages",
		"Comprehension Answers":    "SELECT COUNT(*) FROM comprehension_answers",
	}

	for label, query := range queries {
		var count int64
		err := db.QueryRow(query).Scan(&count)
		if err != nil {
			log.Printf("Error counting %s: %v", label, err)
			continue
		}
		fmt.Printf("%-30s: %d\n", label, count)
	}
}
