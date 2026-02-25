package multiplayer

import "errors"

var (
	// Room errors
	ErrRoomNotFound    = errors.New("room not found")
	ErrRoomFull        = errors.New("room is full")
	ErrRoomNotReady    = errors.New("room is not ready to start")
	ErrInvalidRoomName = errors.New("invalid room name")

	// Player errors
	ErrPlayerNotInRoom    = errors.New("player not in room")
	ErrPlayerAlreadyInRoom = errors.New("player already in room")
	ErrPlayerNotFound     = errors.New("player not found")
	ErrInvalidProgress    = errors.New("invalid progress data")

	// State errors
	ErrInvalidState     = errors.New("invalid room state for this operation")
	ErrAlreadyStarted   = errors.New("race has already started")
	ErrAlreadyFinished  = errors.New("race has already finished")
	ErrNotEnoughPlayers = errors.New("not enough players to start race")
)
