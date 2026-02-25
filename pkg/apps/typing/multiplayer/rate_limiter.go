package multiplayer

import (
	"sync"
	"time"
)

// RateLimiter implements token bucket rate limiting
type RateLimiter struct {
	tokens    int
	maxTokens int
	ticker    *time.Ticker
	mu        sync.Mutex
}

// NewRateLimiter creates a new rate limiter
func NewRateLimiter(maxMessagesPerSecond int) *RateLimiter {
	rl := &RateLimiter{
		tokens:    maxMessagesPerSecond,
		maxTokens: maxMessagesPerSecond,
	}

	// Refill tokens at the specified rate
	rl.ticker = time.NewTicker(time.Second / time.Duration(maxMessagesPerSecond))
	go func() {
		for range rl.ticker.C {
			rl.mu.Lock()
			if rl.tokens < rl.maxTokens {
				rl.tokens++
			}
			rl.mu.Unlock()
		}
	}()

	return rl
}

// Allow checks if a message is allowed under the rate limit
func (rl *RateLimiter) Allow() bool {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	if rl.tokens > 0 {
		rl.tokens--
		return true
	}
	return false
}

// Stop stops the rate limiter
func (rl *RateLimiter) Stop() {
	if rl.ticker != nil {
		rl.ticker.Stop()
	}
}

// Validator provides progress validation
type Validator struct {
	lastPosition   int
	lastValidTime  time.Time
	messageCount   int
	rateLimiter    *RateLimiter
}

// NewValidator creates a new progress validator
func NewValidator() *Validator {
	return &Validator{
		lastPosition:  0,
		lastValidTime: time.Now(),
		messageCount:  0,
		rateLimiter:   NewRateLimiter(20), // Max 20 messages/sec
	}
}

// ValidateProgress validates typing progress
func (v *Validator) ValidateProgress(position int, wpm int, accuracy float64) error {
	// Rate limit check
	if !v.rateLimiter.Allow() {
		return ErrInvalidProgress
	}

	// Check position doesn't go backwards
	if position < v.lastPosition {
		return ErrInvalidProgress
	}

	// Check position doesn't skip >5 chars
	if position-v.lastPosition > 5 {
		return ErrInvalidProgress
	}

	// Check WPM is reasonable (world record is ~216)
	if wpm < 0 || wpm > 250 {
		return ErrInvalidProgress
	}

	// Check accuracy is valid
	if accuracy < 0 || accuracy > 100 {
		return ErrInvalidProgress
	}

	v.lastPosition = position
	v.lastValidTime = time.Now()
	v.messageCount++

	return nil
}

// Close stops the validator
func (v *Validator) Close() {
	if v.rateLimiter != nil {
		v.rateLimiter.Stop()
	}
}
