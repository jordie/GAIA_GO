package multiplayer

// MessageType represents the type of WebSocket message
type MessageType string

const (
	// Client to Server messages
	MsgTypeJoin     MessageType = "join"
	MsgTypeReady    MessageType = "ready"
	MsgTypeProgress MessageType = "progress"
	MsgTypeFinish   MessageType = "finish"
	MsgTypeLeave    MessageType = "leave"
	MsgTypePing     MessageType = "ping"

	// Server to Client messages
	MsgTypePlayerJoined    MessageType = "player_joined"
	MsgTypePlayerLeft      MessageType = "player_left"
	MsgTypePlayerReady     MessageType = "player_ready"
	MsgTypeCountdown       MessageType = "countdown"
	MsgTypeRaceStart       MessageType = "race_start"
	MsgTypePlayerUpdate    MessageType = "player_update"
	MsgTypePlayerFinished  MessageType = "player_finished"
	MsgTypeRaceComplete    MessageType = "race_complete"
	MsgTypeError           MessageType = "error"
	MsgTypePong            MessageType = "pong"
)

// ==================== Base Message ====================

// WSMessage is the base structure for all WebSocket messages
type WSMessage struct {
	Type    MessageType `json:"type"`
	RoomID  string      `json:"room_id,omitempty"`
	Payload interface{} `json:"payload,omitempty"`
}

// ==================== Client to Server Messages ====================

// JoinPayload contains join request data
type JoinPayload struct {
	RoomID       string `json:"room_id"`
	Username     string `json:"username"`
	UserID       int64  `json:"user_id"`
}

// ReadyPayload contains ready status
type ReadyPayload struct {
	IsReady bool `json:"is_ready"`
}

// ProgressPayload contains typing progress
type ProgressPayload struct {
	Position  int     `json:"position"`
	WPM       int     `json:"wpm"`
	Accuracy  float64 `json:"accuracy"`
	Timestamp int64   `json:"timestamp"`
}

// FinishPayload contains race completion data
type FinishPayload struct {
	WPM       int     `json:"wpm"`
	Accuracy  float64 `json:"accuracy"`
	RaceTime  float64 `json:"race_time"`
	Timestamp int64   `json:"timestamp"`
}

// ==================== Server to Client Messages ====================

// PlayerJoinedPayload sent when a player joins
type PlayerJoinedPayload struct {
	UserID   int64  `json:"user_id"`
	Username string `json:"username"`
	CarEmoji string `json:"car_emoji"`
	Placement int    `json:"placement"`
	TotalPlayers int `json:"total_players"`
}

// PlayerLeftPayload sent when a player leaves
type PlayerLeftPayload struct {
	UserID   int64  `json:"user_id"`
	Username string `json:"username"`
	TotalPlayers int `json:"total_players"`
}

// PlayerReadyPayload sent when ready status changes
type PlayerReadyPayload struct {
	UserID   int64 `json:"user_id"`
	Username string `json:"username"`
	IsReady  bool  `json:"is_ready"`
	ReadyCount int `json:"ready_count"`
	TotalPlayers int `json:"total_players"`
}

// CountdownPayload sent during countdown
type CountdownPayload struct {
	Number int `json:"number"` // 3, 2, 1, 0
}

// RaceStartPayload sent when race starts
type RaceStartPayload struct {
	RaceText  string `json:"race_text"`
	StartTime int64  `json:"start_time"`
	Players   []RacePlayerInfo `json:"players"`
}

// RacePlayerInfo contains info about a player in the race
type RacePlayerInfo struct {
	UserID   int64  `json:"user_id"`
	Username string `json:"username"`
	CarEmoji string `json:"car_emoji"`
	Placement int    `json:"placement"`
}

// PlayerUpdatePayload sent when player makes progress
type PlayerUpdatePayload struct {
	UserID   int64  `json:"user_id"`
	Username string `json:"username"`
	Position int    `json:"position"`
	WPM      int    `json:"wpm"`
	Accuracy float64 `json:"accuracy"`
	Placement int    `json:"placement"`
}

// PlayerFinishedPayload sent when a player finishes
type PlayerFinishedPayload struct {
	UserID   int64   `json:"user_id"`
	Username string  `json:"username"`
	WPM      int     `json:"wpm"`
	Accuracy float64 `json:"accuracy"`
	RaceTime float64 `json:"race_time"`
	Placement int     `json:"placement"`
	FinishedAt int64  `json:"finished_at"`
}

// RaceCompletePayload sent when all players finish
type RaceCompletePayload struct {
	Results []RaceResult `json:"results"`
}

// RaceResult contains final race results for a player
type RaceResult struct {
	UserID   int64   `json:"user_id"`
	Username string  `json:"username"`
	Placement int    `json:"placement"`
	WPM      int     `json:"wpm"`
	Accuracy float64 `json:"accuracy"`
	RaceTime float64 `json:"race_time"`
	XPEarned int     `json:"xp_earned"`
	CarEmoji string  `json:"car_emoji"`
}

// ErrorPayload contains error information
type ErrorPayload struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}
