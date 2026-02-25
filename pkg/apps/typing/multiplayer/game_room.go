package multiplayer

import (
	"database/sql"
	"encoding/json"
	"log"
	"sort"
	"sync"
	"time"
)

// RoomState represents the state of a game room
type RoomState string

const (
	StateWaiting   RoomState = "waiting"
	StateCountdown RoomState = "countdown"
	StateRacing    RoomState = "racing"
	StateFinished  RoomState = "finished"
)

// GameRoom represents an active multiplayer race room
type GameRoom struct {
	ID              string
	Players         map[int64]*PlayerConnection
	PlayersMutex    sync.RWMutex
	RaceText        string
	State           RoomState
	StateMutex      sync.RWMutex
	MaxPlayers      int
	MinPlayers      int
	CreatedAt       time.Time
	StartedAt       time.Time
	FinishedAt      time.Time
	HostUserID      int64
	RoomName        string
	Difficulty      string
	WordCount       int
	CountdownTicker *time.Ticker
	RaceTimeout     *time.Timer
	DB              *sql.DB
	carEmojis       []string
}

// NewGameRoom creates a new game room
func NewGameRoom(roomID, roomName, raceText string, hostUserID int64, db *sql.DB) *GameRoom {
	return &GameRoom{
		ID:         roomID,
		RoomName:   roomName,
		RaceText:   raceText,
		HostUserID: hostUserID,
		Players:    make(map[int64]*PlayerConnection),
		State:      StateWaiting,
		MaxPlayers: 4,
		MinPlayers: 2,
		CreatedAt:  time.Now(),
		DB:         db,
		Difficulty: "medium",
		WordCount:  30,
		carEmojis:  []string{"🚗", "🚙", "🚕", "🏎️"},
	}
}

// ==================== Player Management ====================

// AddPlayer adds a player to the room
func (r *GameRoom) AddPlayer(player *PlayerConnection) error {
	r.PlayersMutex.Lock()
	defer r.PlayersMutex.Unlock()

	// Check if room is full
	if len(r.Players) >= r.MaxPlayers {
		return ErrRoomFull
	}

	// Check if player already in room
	if _, exists := r.Players[player.UserID]; exists {
		return ErrPlayerAlreadyInRoom
	}

	// Assign car emoji based on placement
	placement := len(r.Players) + 1
	player.SetCarEmoji(r.carEmojis[(placement-1)%len(r.carEmojis)])
	player.SetPlacement(placement)

	// Add player
	r.Players[player.UserID] = player

	// Notify all players
	r.broadcastPlayerJoined(player, len(r.Players))

	return nil
}

// RemovePlayer removes a player from the room
func (r *GameRoom) RemovePlayer(userID int64) {
	r.PlayersMutex.Lock()
	defer r.PlayersMutex.Unlock()

	if _, exists := r.Players[userID]; !exists {
		return
	}

	player := r.Players[userID]
	delete(r.Players, userID)

	// Notify all players
	r.broadcastPlayerLeft(player, len(r.Players))

	// If room is now empty, mark for cleanup
	if r.GetPlayerCount() == 0 {
		r.SetState(StateFinished)
	}
}

// HandlePlayerDisconnect handles abrupt player disconnection
func (r *GameRoom) HandlePlayerDisconnect(userID int64) {
	r.PlayersMutex.Lock()
	defer r.PlayersMutex.Unlock()

	if _, exists := r.Players[userID]; !exists {
		return
	}

	player := r.Players[userID]
	delete(r.Players, userID)

	// Notify all players
	r.broadcastPlayerLeft(player, len(r.Players))

	// If room is now empty, mark for cleanup
	if r.GetPlayerCount() == 0 {
		r.SetState(StateFinished)
	}
}

// ==================== State Management ====================

// GetState returns the current room state
func (r *GameRoom) GetState() RoomState {
	r.StateMutex.RLock()
	defer r.StateMutex.RUnlock()
	return r.State
}

// SetState sets the room state
func (r *GameRoom) SetState(state RoomState) {
	r.StateMutex.Lock()
	defer r.StateMutex.Unlock()
	r.State = state
}

// ==================== Ready System ====================

// SetPlayerReady sets a player's ready status
func (r *GameRoom) SetPlayerReady(userID int64, isReady bool) error {
	r.PlayersMutex.Lock()
	player, exists := r.Players[userID]
	r.PlayersMutex.Unlock()

	if !exists {
		return ErrPlayerNotInRoom
	}

	player.SetReady(isReady)

	// Count ready players
	readyCount := r.countReadyPlayers()
	totalPlayers := r.GetPlayerCount()

	// Broadcast ready status change
	r.broadcastPlayerReady(player, readyCount, totalPlayers)

	// Check if all players ready and we have minimum
	if readyCount == totalPlayers && totalPlayers >= r.MinPlayers {
		r.startCountdown()
	}

	return nil
}

// countReadyPlayers counts how many players are ready
func (r *GameRoom) countReadyPlayers() int {
	r.PlayersMutex.RLock()
	defer r.PlayersMutex.RUnlock()

	count := 0
	for _, player := range r.Players {
		if player.GetReady() {
			count++
		}
	}
	return count
}

// GetPlayerCount returns total players in room
func (r *GameRoom) GetPlayerCount() int {
	r.PlayersMutex.RLock()
	defer r.PlayersMutex.RUnlock()
	return len(r.Players)
}

// ==================== Race State Machine ====================

// startCountdown initiates the 3-second countdown
func (r *GameRoom) startCountdown() {
	r.SetState(StateCountdown)

	go func() {
		for i := 3; i > 0; i-- {
			r.broadcastCountdown(i)
			time.Sleep(1 * time.Second)
		}
		r.startRace()
	}()
}

// startRace starts the actual race
func (r *GameRoom) startRace() {
	r.SetState(StateRacing)
	r.StartedAt = time.Now()

	// Reset player progress
	r.PlayersMutex.RLock()
	for _, player := range r.Players {
		player.ResetProgress()
	}
	r.PlayersMutex.RUnlock()

	// Broadcast race start
	r.broadcastRaceStart()

	// Set race timeout (5 minutes max)
	r.RaceTimeout = time.AfterFunc(5*time.Minute, func() {
		r.finishRace()
	})
}

// UpdatePlayerProgress updates a player's typing progress
func (r *GameRoom) UpdatePlayerProgress(userID int64, payload ProgressPayload) error {
	// Only allow during racing state
	if r.GetState() != StateRacing {
		return ErrInvalidState
	}

	r.PlayersMutex.RLock()
	player, exists := r.Players[userID]
	r.PlayersMutex.RUnlock()

	if !exists {
		return ErrPlayerNotInRoom
	}

	// Validate and update progress
	if err := player.UpdateProgress(payload.Position, payload.WPM, payload.Accuracy); err != nil {
		return err
	}

	// Update placement based on progress
	r.updatePlacements()

	// Broadcast progress update
	r.broadcastPlayerUpdate(player)

	return nil
}

// MarkPlayerFinished marks a player as finished
func (r *GameRoom) MarkPlayerFinished(userID int64, payload FinishPayload) {
	r.PlayersMutex.RLock()
	player, exists := r.Players[userID]
	r.PlayersMutex.RUnlock()

	if !exists {
		return
	}

	// Mark finished
	player.SetFinished(payload.WPM, payload.Accuracy, payload.RaceTime)

	// Update placements
	r.updatePlacements()

	// Broadcast player finished
	r.broadcastPlayerFinished(player)

	// Check if all players finished
	if r.allPlayersFinished() {
		r.finishRace()
	}
}

// allPlayersFinished checks if all players have finished
func (r *GameRoom) allPlayersFinished() bool {
	r.PlayersMutex.RLock()
	defer r.PlayersMutex.RUnlock()

	if len(r.Players) == 0 {
		return false
	}

	for _, player := range r.Players {
		if !player.IsPlayerFinished() {
			return false
		}
	}
	return true
}

// updatePlacements recalculates player placements based on progress
func (r *GameRoom) updatePlacements() {
	r.PlayersMutex.RLock()
	defer r.PlayersMutex.RUnlock()

	// Create sorted list of players
	type playerSort struct {
		player   *PlayerConnection
		position int
		finished bool
	}

	var players []playerSort
	for _, player := range r.Players {
		pos, _, _, finished := player.GetStats()
		players = append(players, playerSort{
			player:   player,
			position: pos,
			finished: finished,
		})
	}

	// Sort by finished first, then by position
	sort.Slice(players, func(i, j int) bool {
		// Finished players first
		if players[i].finished && !players[j].finished {
			return true
		}
		if !players[i].finished && players[j].finished {
			return false
		}

		// Among finished, sort by position descending
		if players[i].finished && players[j].finished {
			return players[i].position > players[j].position
		}

		// Among non-finished, sort by position descending
		return players[i].position > players[j].position
	})

	// Assign placements
	for idx, p := range players {
		p.player.SetPlacement(idx + 1)
	}
}

// finishRace completes the race and saves results
func (r *GameRoom) finishRace() {
	r.SetState(StateFinished)
	r.FinishedAt = time.Now()

	if r.RaceTimeout != nil {
		r.RaceTimeout.Stop()
	}

	// Cancel countdown if still running
	if r.CountdownTicker != nil {
		r.CountdownTicker.Stop()
	}

	// Get final results
	results := r.getFinalResults()

	// Save results to database
	r.saveRaceResults(results)

	// Broadcast race complete
	r.broadcastRaceComplete(results)
}

// getFinalResults gets final race results for all players
func (r *GameRoom) getFinalResults() []RaceResult {
	r.PlayersMutex.RLock()
	defer r.PlayersMutex.RUnlock()

	var results []RaceResult
	for _, player := range r.Players {
		// Get final stats
		placement := player.GetPlacement()
		xpEarned := calculateRaceXP(player, placement)

		results = append(results, RaceResult{
			UserID:   player.UserID,
			Username: player.Username,
			Placement: placement,
			WPM:      player.FinalWPM,
			Accuracy: player.FinalAccuracy,
			RaceTime: player.RaceTime,
			XPEarned: xpEarned,
			CarEmoji: player.GetCarEmoji(),
		})
	}

	// Sort by placement
	sort.Slice(results, func(i, j int) bool {
		return results[i].Placement < results[j].Placement
	})

	return results
}

// saveRaceResults saves race results to database
func (r *GameRoom) saveRaceResults(results []RaceResult) {
	if r.DB == nil {
		return
	}

	// Create race_rooms record
	_, err := r.DB.Exec(`
		INSERT INTO race_rooms (id, name, host_user_id, race_text, word_count, difficulty, max_players, min_players, state, created_at, started_at, finished_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`, r.ID, r.RoomName, r.HostUserID, r.RaceText, r.WordCount, r.Difficulty, r.MaxPlayers, r.MinPlayers,
		string(StateFinished), r.CreatedAt, r.StartedAt, r.FinishedAt)

	if err != nil {
		log.Printf("[GameRoom] Error saving race_rooms: %v\n", err)
		return
	}

	// Save participants
	for _, result := range results {
		_, _ = r.DB.Exec(`
			INSERT INTO race_participants (race_id, user_id, username, placement, wpm, accuracy, race_time, finished_at, xp_earned)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
		`, r.ID, result.UserID, result.Username, result.Placement, result.WPM, result.Accuracy, result.RaceTime,
			time.Now(), result.XPEarned)
	}
}

// Broadcast sends message to all players in room
func (r *GameRoom) Broadcast(message []byte) {
	r.PlayersMutex.RLock()
	defer r.PlayersMutex.RUnlock()

	for _, player := range r.Players {
		select {
		case player.SendChan <- message:
			// Queued successfully
		default:
			// Channel full, skip (slow client)
			log.Printf("[GameRoom] Send channel full for player %d\n", player.UserID)
		}
	}
}

// ==================== Broadcasting Helpers ====================

func (r *GameRoom) broadcastPlayerJoined(player *PlayerConnection, totalPlayers int) {
	msg := WSMessage{
		Type:   MsgTypePlayerJoined,
		RoomID: r.ID,
		Payload: PlayerJoinedPayload{
			UserID:       player.UserID,
			Username:     player.Username,
			CarEmoji:     player.GetCarEmoji(),
			Placement:    player.GetPlacement(),
			TotalPlayers: totalPlayers,
		},
	}
	r.broadcastMessage(msg)
}

func (r *GameRoom) broadcastPlayerLeft(player *PlayerConnection, totalPlayers int) {
	msg := WSMessage{
		Type:   MsgTypePlayerLeft,
		RoomID: r.ID,
		Payload: PlayerLeftPayload{
			UserID:       player.UserID,
			Username:     player.Username,
			TotalPlayers: totalPlayers,
		},
	}
	r.broadcastMessage(msg)
}

func (r *GameRoom) broadcastPlayerReady(player *PlayerConnection, readyCount, totalPlayers int) {
	msg := WSMessage{
		Type:   MsgTypePlayerReady,
		RoomID: r.ID,
		Payload: PlayerReadyPayload{
			UserID:       player.UserID,
			Username:     player.Username,
			IsReady:      player.GetReady(),
			ReadyCount:   readyCount,
			TotalPlayers: totalPlayers,
		},
	}
	r.broadcastMessage(msg)
}

func (r *GameRoom) broadcastCountdown(number int) {
	msg := WSMessage{
		Type:   MsgTypeCountdown,
		RoomID: r.ID,
		Payload: CountdownPayload{
			Number: number,
		},
	}
	r.broadcastMessage(msg)
}

func (r *GameRoom) broadcastRaceStart() {
	r.PlayersMutex.RLock()
	defer r.PlayersMutex.RUnlock()

	players := make([]RacePlayerInfo, 0)
	for _, player := range r.Players {
		players = append(players, RacePlayerInfo{
			UserID:    player.UserID,
			Username:  player.Username,
			CarEmoji:  player.GetCarEmoji(),
			Placement: player.GetPlacement(),
		})
	}

	msg := WSMessage{
		Type:   MsgTypeRaceStart,
		RoomID: r.ID,
		Payload: RaceStartPayload{
			RaceText:  r.RaceText,
			StartTime: r.StartedAt.Unix(),
			Players:   players,
		},
	}
	r.broadcastMessage(msg)
}

func (r *GameRoom) broadcastPlayerUpdate(player *PlayerConnection) {
	pos, wpm, acc, _ := player.GetStats()
	msg := WSMessage{
		Type:   MsgTypePlayerUpdate,
		RoomID: r.ID,
		Payload: PlayerUpdatePayload{
			UserID:    player.UserID,
			Username:  player.Username,
			Position:  pos,
			WPM:       wpm,
			Accuracy:  acc,
			Placement: player.GetPlacement(),
		},
	}
	r.broadcastMessage(msg)
}

func (r *GameRoom) broadcastPlayerFinished(player *PlayerConnection) {
	msg := WSMessage{
		Type:   MsgTypePlayerFinished,
		RoomID: r.ID,
		Payload: PlayerFinishedPayload{
			UserID:    player.UserID,
			Username:  player.Username,
			WPM:       player.FinalWPM,
			Accuracy:  player.FinalAccuracy,
			RaceTime:  player.RaceTime,
			Placement: player.GetPlacement(),
			FinishedAt: player.FinishedAt.Unix(),
		},
	}
	r.broadcastMessage(msg)
}

func (r *GameRoom) broadcastRaceComplete(results []RaceResult) {
	msg := WSMessage{
		Type:   MsgTypeRaceComplete,
		RoomID: r.ID,
		Payload: RaceCompletePayload{
			Results: results,
		},
	}
	r.broadcastMessage(msg)
}

func (r *GameRoom) broadcastMessage(msg WSMessage) {
	data, _ := json.Marshal(msg)
	r.Broadcast(data)
}

// ==================== Helper Functions ====================

// calculateRaceXP calculates XP for a player (from typing package)
func calculateRaceXP(player *PlayerConnection, placement int) int {
	// Using the same logic as CalculateRaceXP from typing.go
	baseXP := 10
	placementBonus := map[int]int{
		1: 50,
		2: 30,
		3: 15,
		4: 0,
	}

	accuracyBonus := 0
	if player.FinalAccuracy >= 100 {
		accuracyBonus = 25
	} else if player.FinalAccuracy >= 95 {
		accuracyBonus = 15
	}

	speedBonus := 0
	if player.FinalWPM >= 60 {
		speedBonus = 20
	} else if player.FinalWPM >= 40 {
		speedBonus = 10
	}

	bonus := placementBonus[placement]
	if bonus == 0 && placement > 4 {
		bonus = 0
	}

	multiplier := 1.0
	switch player.FinalWPM {
	case 0:
		// Default multiplier
	}

	xp := float64(baseXP+bonus+accuracyBonus+speedBonus) * multiplier
	return int(xp)
}
