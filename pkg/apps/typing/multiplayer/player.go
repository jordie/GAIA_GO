package multiplayer

import (
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

// PlayerConnection represents a connected player in a race
type PlayerConnection struct {
	UserID            int64
	Username          string
	Conn              *websocket.Conn
	SendChan          chan []byte // Buffered for non-blocking sends
	RoomID            string
	CurrentPosition   int
	CurrentWPM        int
	CurrentAccuracy   float64
	IsReady           bool
	HasFinished       bool
	FinishedAt        time.Time
	RaceTime          float64
	FinalWPM          int
	FinalAccuracy     float64
	Placement         int
	CarEmoji          string
	LastProgressTime  time.Time
	MessageCount      int
	Mutex             sync.RWMutex
}

// UpdateProgress updates player's typing progress with validation
func (p *PlayerConnection) UpdateProgress(position int, wpm int, accuracy float64) error {
	p.Mutex.Lock()
	defer p.Mutex.Unlock()

	// Validate position doesn't go backwards
	if position < p.CurrentPosition {
		return ErrInvalidProgress
	}

	// Validate position doesn't skip more than 5 chars (network buffer tolerance)
	if position-p.CurrentPosition > 5 {
		return ErrInvalidProgress
	}

	// Validate WPM is reasonable (world record is ~216)
	if wpm > 250 {
		return ErrInvalidProgress
	}

	// Validate accuracy is 0-100
	if accuracy < 0 || accuracy > 100 {
		return ErrInvalidProgress
	}

	p.CurrentPosition = position
	p.CurrentWPM = wpm
	p.CurrentAccuracy = accuracy
	p.LastProgressTime = time.Now()
	p.MessageCount++

	return nil
}

// SetReady updates the ready status
func (p *PlayerConnection) SetReady(ready bool) {
	p.Mutex.Lock()
	defer p.Mutex.Unlock()
	p.IsReady = ready
}

// GetReady returns the current ready status
func (p *PlayerConnection) GetReady() bool {
	p.Mutex.RLock()
	defer p.Mutex.RUnlock()
	return p.IsReady
}

// SetFinished marks the player as finished with final stats
func (p *PlayerConnection) SetFinished(wpm int, accuracy float64, raceTime float64) {
	p.Mutex.Lock()
	defer p.Mutex.Unlock()
	p.HasFinished = true
	p.FinishedAt = time.Now()
	p.FinalWPM = wpm
	p.FinalAccuracy = accuracy
	p.RaceTime = raceTime
}

// IsPlayerFinished returns whether the player has finished
func (p *PlayerConnection) IsPlayerFinished() bool {
	p.Mutex.RLock()
	defer p.Mutex.RUnlock()
	return p.HasFinished
}

// GetStats returns current player statistics
func (p *PlayerConnection) GetStats() (int, int, float64, bool) {
	p.Mutex.RLock()
	defer p.Mutex.RUnlock()
	return p.CurrentPosition, p.CurrentWPM, p.CurrentAccuracy, p.HasFinished
}

// ResetProgress resets player progress for a new race
func (p *PlayerConnection) ResetProgress() {
	p.Mutex.Lock()
	defer p.Mutex.Unlock()
	p.CurrentPosition = 0
	p.CurrentWPM = 0
	p.CurrentAccuracy = 0
	p.IsReady = false
	p.HasFinished = false
	p.Placement = 0
	p.LastProgressTime = time.Now()
	p.MessageCount = 0
}

// GetPlacement returns the player's placement
func (p *PlayerConnection) GetPlacement() int {
	p.Mutex.RLock()
	defer p.Mutex.RUnlock()
	return p.Placement
}

// SetPlacement sets the player's placement
func (p *PlayerConnection) SetPlacement(placement int) {
	p.Mutex.Lock()
	defer p.Mutex.Unlock()
	p.Placement = placement
}

// SetCarEmoji sets the player's car emoji
func (p *PlayerConnection) SetCarEmoji(emoji string) {
	p.Mutex.Lock()
	defer p.Mutex.Unlock()
	p.CarEmoji = emoji
}

// GetCarEmoji returns the player's car emoji
func (p *PlayerConnection) GetCarEmoji() string {
	p.Mutex.RLock()
	defer p.Mutex.RUnlock()
	return p.CarEmoji
}
