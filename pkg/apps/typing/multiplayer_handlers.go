package typing

import (
	"log"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/jgirmay/GAIA_GO/internal/api"
	"github.com/jgirmay/GAIA_GO/internal/middleware"
	"github.com/jgirmay/GAIA_GO/internal/session"
	"github.com/jgirmay/GAIA_GO/pkg/apps/typing/multiplayer"
)

// RegisterMultiplayerHandlers registers multiplayer-specific handlers
func RegisterMultiplayerHandlers(router *gin.RouterGroup, roomManager *multiplayer.GameRoomManager, wsHub *multiplayer.WebSocketHub, sessionMgr *session.Manager) {
	// HTTP endpoints (lobby management)
	router.POST("/multiplayer/rooms", middleware.RequireAuth(), createRoom(roomManager))
	router.GET("/multiplayer/rooms", listRooms(roomManager))
	router.DELETE("/multiplayer/rooms/:room_id", middleware.RequireAuth(), leaveRoom(roomManager))
	router.GET("/multiplayer/history", middleware.RequireAuth(), getRaceHistory(roomManager))
	router.GET("/multiplayer/stats", middleware.RequireAuth(), getMultiplayerStats(roomManager))

	// WebSocket endpoint
	router.GET("/ws/typing/race/:room_id", handleWebSocket(roomManager, wsHub, sessionMgr))
}

// ==================== Request/Response Types ====================

type CreateRoomRequest struct {
	Name       string `json:"name" binding:"required"`
	Difficulty string `json:"difficulty"`
	WordCount  int    `json:"word_count"`
}

type CreateRoomResponse struct {
	RoomID    string `json:"room_id"`
	RoomName  string `json:"room_name"`
	HostID    int64  `json:"host_id"`
	RaceText  string `json:"race_text"`
	MaxPlayers int    `json:"max_players"`
	Difficulty string `json:"difficulty"`
	State     string `json:"state"`
}

type ListRoomsResponse struct {
	RoomID     string `json:"room_id"`
	RoomName   string `json:"room_name"`
	HostID     int64  `json:"host_id"`
	Players    int    `json:"players"`
	MaxPlayers int    `json:"max_players"`
	Difficulty string `json:"difficulty"`
	CreatedAt  string `json:"created_at"`
}

// ==================== Handlers ====================

// createRoom creates a new multiplayer race room
func createRoom(roomManager *multiplayer.GameRoomManager) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID, _ := middleware.GetUserID(c)

		var req CreateRoomRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			api.RespondWithError(c, api.ErrBadRequest)
			return
		}

		// Set defaults
		if req.Difficulty == "" {
			req.Difficulty = "medium"
		}
		if req.WordCount <= 0 {
			req.WordCount = 30
		}

		// Create room
		room, err := roomManager.CreateRoom(userID, req.Name, req.Difficulty, req.WordCount)
		if err != nil {
			api.RespondWithError(c, api.ErrInternalServer)
			return
		}

		resp := CreateRoomResponse{
			RoomID:     room.ID,
			RoomName:   room.RoomName,
			HostID:     userID,
			RaceText:   room.RaceText,
			MaxPlayers: room.MaxPlayers,
			Difficulty: room.Difficulty,
			State:      string(room.GetState()),
		}

		api.RespondWith(c, http.StatusOK, resp)
	}
}

// listRooms lists available rooms
func listRooms(roomManager *multiplayer.GameRoomManager) gin.HandlerFunc {
	return func(c *gin.Context) {
		rooms := roomManager.ListRooms()

		var resp []ListRoomsResponse
		for _, room := range rooms {
			resp = append(resp, ListRoomsResponse{
				RoomID:     room.ID,
				RoomName:   room.RoomName,
				HostID:     room.HostUserID,
				Players:    room.GetPlayerCount(),
				MaxPlayers: room.MaxPlayers,
				Difficulty: room.Difficulty,
				CreatedAt:  room.CreatedAt.Format("2006-01-02T15:04:05Z"),
			})
		}

		if resp == nil {
			resp = []ListRoomsResponse{}
		}

		api.RespondWith(c, http.StatusOK, gin.H{
			"rooms": resp,
		})
	}
}

// leaveRoom removes a player from a room
func leaveRoom(roomManager *multiplayer.GameRoomManager) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID, _ := middleware.GetUserID(c)
		roomID := c.Param("room_id")

		room, err := roomManager.GetRoom(roomID)
		if err != nil {
			api.RespondWithError(c, api.ErrNotFound)
			return
		}

		room.RemovePlayer(userID)

		api.RespondWith(c, http.StatusOK, gin.H{
			"success": true,
			"message": "Left room successfully",
		})
	}
}

// getRaceHistory gets user's race history
func getRaceHistory(roomManager *multiplayer.GameRoomManager) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID, _ := middleware.GetUserID(c)

		limitStr := c.DefaultQuery("limit", "20")
		limit, _ := strconv.Atoi(limitStr)

		history, err := roomManager.GetUserRaceHistory(userID, limit)
		if err != nil {
			api.RespondWithError(c, api.ErrInternalServer)
			return
		}

		if history == nil {
			history = []map[string]interface{}{}
		}

		api.RespondWith(c, http.StatusOK, gin.H{
			"history": history,
		})
	}
}

// getMultiplayerStats gets user's multiplayer stats
func getMultiplayerStats(roomManager *multiplayer.GameRoomManager) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID, _ := middleware.GetUserID(c)

		stats, err := roomManager.GetUserStats(userID)
		if err != nil {
			api.RespondWithError(c, api.ErrInternalServer)
			return
		}

		api.RespondWith(c, http.StatusOK, stats)
	}
}

// handleWebSocket handles WebSocket connections for racing
func handleWebSocket(roomManager *multiplayer.GameRoomManager, wsHub *multiplayer.WebSocketHub, sessionMgr *session.Manager) gin.HandlerFunc {
	return func(c *gin.Context) {
		roomID := c.Param("room_id")

		// Verify room exists
		_, err := roomManager.GetRoom(roomID)
		if err != nil {
			c.JSON(http.StatusNotFound, gin.H{"error": "Room not found"})
			return
		}

		// Upgrade connection
		conn, err := wsHub.UpgradeConnection(c.Writer, c.Request, roomID)
		if err != nil {
			log.Printf("[WebSocket] Failed to upgrade connection: %v\n", err)
			c.JSON(http.StatusBadRequest, gin.H{"error": "Failed to upgrade connection"})
			return
		}

		// Get player from hub
		player := wsHub.GetPlayer(conn)
		if player == nil {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
			return
		}

		// Handle connection
		wsHub.HandleConnection(conn, player)
	}
}
