package multiplayer

import (
	"database/sql"
	"log"
	"regexp"
	"sync"
	"time"

	"github.com/google/uuid"
)

// GameRoomManager manages all active game rooms
type GameRoomManager struct {
	db       *sql.DB
	rooms    map[string]*GameRoom
	mu       sync.RWMutex
	maxRooms int
	tyingApp interface{} // TypingApp reference for text generation
}

// NewGameRoomManager creates a new room manager
func NewGameRoomManager(db *sql.DB, typingApp interface{}) *GameRoomManager {
	m := &GameRoomManager{
		db:       db,
		rooms:    make(map[string]*GameRoom),
		maxRooms: 1000,
		tyingApp: typingApp,
	}

	// Start cleanup goroutine
	go m.cleanupStaleRooms()

	return m
}

// ==================== Room Lifecycle ====================

// CreateRoom creates a new game room
func (m *GameRoomManager) CreateRoom(hostUserID int64, roomName, difficulty string, wordCount int) (*GameRoom, error) {
	// Validate inputs
	if !isValidRoomName(roomName) {
		return nil, ErrInvalidRoomName
	}

	// Check room count
	m.mu.RLock()
	roomCount := len(m.rooms)
	m.mu.RUnlock()
	if roomCount >= m.maxRooms {
		return nil, ErrRoomNotFound // Generic error for resource limit
	}

	// Generate room ID
	roomID := uuid.New().String()

	// Generate race text (using simple fallback if app not available)
	raceText := generateRaceText(wordCount)

	// Create room
	room := NewGameRoom(roomID, roomName, raceText, hostUserID, m.db)
	room.Difficulty = difficulty
	room.WordCount = wordCount

	// Store room
	m.mu.Lock()
	m.rooms[roomID] = room
	m.mu.Unlock()

	// Save to database
	_, err := m.db.Exec(`
		INSERT INTO race_rooms (id, name, host_user_id, race_text, word_count, difficulty, max_players, min_players, state, created_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`, roomID, roomName, hostUserID, raceText, wordCount, difficulty, 4, 2, string(StateWaiting), time.Now())

	if err != nil {
		// Remove from memory if DB insert fails
		m.mu.Lock()
		delete(m.rooms, roomID)
		m.mu.Unlock()
		return nil, err
	}

	return room, nil
}

// GetRoom retrieves a room by ID
func (m *GameRoomManager) GetRoom(roomID string) (*GameRoom, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	room, exists := m.rooms[roomID]
	if !exists {
		return nil, ErrRoomNotFound
	}

	return room, nil
}

// ListRooms returns available rooms (waiting state)
func (m *GameRoomManager) ListRooms() []*GameRoom {
	m.mu.RLock()
	defer m.mu.RUnlock()

	var rooms []*GameRoom
	for _, room := range m.rooms {
		if room.GetState() == StateWaiting {
			rooms = append(rooms, room)
		}
	}

	return rooms
}

// DeleteRoom removes a room
func (m *GameRoomManager) DeleteRoom(roomID string) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	if _, exists := m.rooms[roomID]; !exists {
		return ErrRoomNotFound
	}

	delete(m.rooms, roomID)
	return nil
}

// ==================== Cleanup ====================

// cleanupStaleRooms removes finished rooms periodically
func (m *GameRoomManager) cleanupStaleRooms() {
	ticker := time.NewTicker(1 * time.Minute)
	defer ticker.Stop()

	for range ticker.C {
		m.mu.Lock()

		now := time.Now()
		for id, room := range m.rooms {
			// Remove rooms that finished more than 5 minutes ago
			if room.GetState() == StateFinished && now.Sub(room.FinishedAt) > 5*time.Minute {
				delete(m.rooms, id)
			}

			// Remove empty waiting rooms older than 30 minutes
			if room.GetState() == StateWaiting {
				if room.GetPlayerCount() == 0 && now.Sub(room.CreatedAt) > 30*time.Minute {
					delete(m.rooms, id)
				}
			}
		}

		m.mu.Unlock()

		// Log stats
		m.mu.RLock()
		roomCount := len(m.rooms)
		m.mu.RUnlock()

		log.Printf("[GameRoomManager] Active rooms: %d\n", roomCount)
	}
}

// ==================== Room History ====================

// GetUserRaceHistory retrieves race history for a user
func (m *GameRoomManager) GetUserRaceHistory(userID int64, limit int) ([]map[string]interface{}, error) {
	if limit <= 0 || limit > 100 {
		limit = 20
	}

	rows, err := m.db.Query(`
		SELECT rr.id, rr.name, rr.created_at, rp.placement, rp.wpm, rp.accuracy, rp.race_time, rp.xp_earned
		FROM race_rooms rr
		JOIN race_participants rp ON rr.id = rp.race_id
		WHERE rp.user_id = ? AND rr.state = ?
		ORDER BY rr.created_at DESC
		LIMIT ?
	`, userID, string(StateFinished), limit)

	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var history []map[string]interface{}
	for rows.Next() {
		var (
			roomID    string
			roomName  string
			createdAt time.Time
			placement int
			wpm       int
			accuracy  float64
			raceTime  float64
			xpEarned  int
		)

		if err := rows.Scan(&roomID, &roomName, &createdAt, &placement, &wpm, &accuracy, &raceTime, &xpEarned); err != nil {
			continue
		}

		history = append(history, map[string]interface{}{
			"room_id":    roomID,
			"room_name":  roomName,
			"created_at": createdAt,
			"placement":  placement,
			"wpm":        wpm,
			"accuracy":   accuracy,
			"race_time":  raceTime,
			"xp_earned":  xpEarned,
		})
	}

	return history, nil
}

// GetUserStats gets multiplayer racing stats for a user
func (m *GameRoomManager) GetUserStats(userID int64) (map[string]interface{}, error) {
	var (
		totalRaces     int
		wins           int
		podiums        int
		totalXP        int
		avgWPM         float64
		avgAccuracy    float64
	)

	// Get stats from race_participants
	err := m.db.QueryRow(`
		SELECT
			COUNT(*) as total_races,
			SUM(CASE WHEN placement = 1 THEN 1 ELSE 0 END) as wins,
			SUM(CASE WHEN placement <= 3 THEN 1 ELSE 0 END) as podiums,
			SUM(xp_earned) as total_xp,
			AVG(wpm) as avg_wpm,
			AVG(accuracy) as avg_accuracy
		FROM race_participants
		WHERE user_id = ?
	`, userID).Scan(&totalRaces, &wins, &podiums, &totalXP, &avgWPM, &avgAccuracy)

	if err != nil && err != sql.ErrNoRows {
		return nil, err
	}

	return map[string]interface{}{
		"total_races":  totalRaces,
		"wins":         wins,
		"podiums":      podiums,
		"total_xp":     totalXP,
		"avg_wpm":      int(avgWPM),
		"avg_accuracy": avgAccuracy,
	}, nil
}

// ==================== Helper Functions ====================

// isValidRoomName validates room name
func isValidRoomName(name string) bool {
	if len(name) < 1 || len(name) > 50 {
		return false
	}

	// Allow alphanumeric, spaces, and hyphens
	matched, _ := regexp.MatchString(`^[a-zA-Z0-9\s\-]+$`, name)
	return matched
}

// generateRaceText generates race text (fallback implementation)
func generateRaceText(wordCount int) string {
	if wordCount <= 0 {
		wordCount = 30
	}

	// Common words list
	words := []string{
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

	result := ""
	for i := 0; i < wordCount; i++ {
		if i > 0 {
			result += " "
		}
		result += words[i%len(words)]
	}

	return result
}
