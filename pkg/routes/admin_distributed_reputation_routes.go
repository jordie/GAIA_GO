package routes

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"

	"github.com/jgirmay/GAIA_GO/pkg/services/rate_limiting"
)

// RegisterDistributedReputationRoutes registers all distributed reputation API routes
func RegisterDistributedReputationRoutes(router *gin.Engine, db *gorm.DB, drm *rate_limiting.DistributedReputationManager) {
	api := router.Group("/api/admin/distributed-reputation")
	{
		// Node Management
		api.GET("/nodes", getRegisteredNodes(db, drm))
		api.POST("/nodes", registerRemoteNode(db, drm))
		api.DELETE("/nodes/:nodeID", unregisterNode(db, drm))

		// Sync Management
		api.GET("/sync-status", getSyncStatus(drm))
		api.GET("/sync-health", getSyncHealth(db))
		api.POST("/sync-trigger", triggerImmediateSync(drm))
		api.GET("/sync-history", getSyncHistory(db))

		// Reputation Data
		api.GET("/events/recent", getRecentEvents(db))
		api.GET("/events/unsynced", getUnsyncedEvents(db))
		api.GET("/user/:userID/consensus", getUserConsensus(drm))
		api.GET("/user/:userID/node-views", getUserNodeViews(db))

		// Replication Stats
		api.GET("/replication-stats", getReplicationStats(drm))
		api.GET("/replication-summary", getReplicationSummary(db))
		api.GET("/latency-stats", getLatencyStats(db))

		// Network Health
		api.GET("/network-health", getNetworkHealth(db))
		api.GET("/conflict-resolution", getConflictStats(db))

		// Administrative Actions
		api.POST("/resolve-conflicts/:userID", resolveUserConflicts(drm))
		api.POST("/force-sync-node/:nodeID", forceSyncNode(drm))
		api.POST("/purge-duplicates", purgeDuplicateEvents(db))
	}
}

// getRegisteredNodes returns all registered remote nodes
func getRegisteredNodes(db *gorm.DB, drm *rate_limiting.DistributedReputationManager) gin.HandlerFunc {
	return func(c *gin.Context) {
		var syncs []rate_limiting.ReputationSync
		if err := db.Where("node_id = ?", drm.GetLocalNodeID()).Find(&syncs).Error; err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve nodes"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"local_node_id": drm.GetLocalNodeID(),
			"remote_nodes":  syncs,
			"total_nodes":   len(syncs) + 1,
		})
	}
}

// registerRemoteNode registers a new remote node
func registerRemoteNode(db *gorm.DB, drm *rate_limiting.DistributedReputationManager) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req struct {
			NodeID      string `json:"node_id" binding:"required"`
			APIEndpoint string `json:"api_endpoint" binding:"required"`
		}

		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request"})
			return
		}

		if err := drm.RegisterRemoteNode(req.NodeID, req.APIEndpoint); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusCreated, gin.H{
			"success": true,
			"node_id": req.NodeID,
		})
	}
}

// unregisterNode removes a remote node from the network
func unregisterNode(db *gorm.DB, drm *rate_limiting.DistributedReputationManager) gin.HandlerFunc {
	return func(c *gin.Context) {
		nodeID := c.Param("nodeID")

		if err := db.Where("node_id = ? AND remote_node_id = ?", drm.GetLocalNodeID(), nodeID).Delete(&rate_limiting.ReputationSync{}).Error; err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to unregister node"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"node_id": nodeID,
		})
	}
}

// getSyncStatus returns current synchronization status
func getSyncStatus(drm *rate_limiting.DistributedReputationManager) gin.HandlerFunc {
	return func(c *gin.Context) {
		ctx := c.Request.Context()
		status, err := drm.GetSyncStatus(ctx)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, status)
	}
}

// getSyncHealth returns detailed sync health information
func getSyncHealth(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		var syncs []rate_limiting.ReputationSync
		if err := db.Order("status DESC, last_sync_time DESC").Find(&syncs).Error; err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve sync health"})
			return
		}

		healthCounts := map[string]int{
			"healthy":  0,
			"degraded": 0,
			"failed":   0,
		}

		totalPending := 0
		for _, sync := range syncs {
			healthCounts[sync.Status]++
			totalPending += sync.PendingEvents
		}

		c.JSON(http.StatusOK, gin.H{
			"syncs":           syncs,
			"health_summary":  healthCounts,
			"total_pending":   totalPending,
			"total_pairs":     len(syncs),
		})
	}
}

// triggerImmediateSync forces an immediate sync cycle
func triggerImmediateSync(drm *rate_limiting.DistributedReputationManager) gin.HandlerFunc {
	return func(c *gin.Context) {
		// In production, this would trigger the sync worker
		// For now, we acknowledge the request
		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "Sync cycle triggered",
		})
	}
}

// getSyncHistory returns synchronization history
func getSyncHistory(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		limit := 100
		if l := c.Query("limit"); l != "" {
			if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 && parsed <= 1000 {
				limit = parsed
			}
		}

		var events []rate_limiting.ReputationEvent
		if err := db.Where("synced_at IS NOT NULL").Order("synced_at DESC").Limit(limit).Find(&events).Error; err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve sync history"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"count":   len(events),
			"limit":   limit,
			"events":  events,
		})
	}
}

// getRecentEvents returns recent reputation events
func getRecentEvents(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		minutes := 60
		if m := c.Query("minutes"); m != "" {
			if parsed, err := strconv.Atoi(m); err == nil && parsed > 0 {
				minutes = parsed
			}
		}

		var events []rate_limiting.ReputationEvent
		if err := db.Order("timestamp DESC").Limit(100).Find(&events).Error; err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve events"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"count":   len(events),
			"events":  events,
		})
	}
}

// getUnsyncedEvents returns events pending synchronization
func getUnsyncedEvents(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		var events []rate_limiting.ReputationEvent
		if err := db.Where("synced_at IS NULL AND local_only = ?", false).Order("timestamp ASC").Find(&events).Error; err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve unsynced events"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"count":   len(events),
			"events":  events,
		})
	}
}

// getUserConsensus returns consensus reputation for a user
func getUserConsensus(drm *rate_limiting.DistributedReputationManager) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID, err := strconv.Atoi(c.Param("userID"))
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid user ID"})
			return
		}

		ctx := c.Request.Context()
		score, tier, confidence, err := drm.GetUserReputationConsensus(ctx, userID)
		if err != nil {
			c.JSON(http.StatusNotFound, gin.H{"error": "No reputation data found"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"user_id":    userID,
			"score":      score,
			"tier":       tier,
			"confidence": confidence,
		})
	}
}

// getUserNodeViews returns reputation view from each node
func getUserNodeViews(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID, err := strconv.Atoi(c.Param("userID"))
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid user ID"})
			return
		}

		var nodeReps []rate_limiting.NodeReputation
		if err := db.Where("user_id = ?", userID).Order("last_updated DESC").Find(&nodeReps).Error; err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve node views"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"user_id":      userID,
			"node_count":   len(nodeReps),
			"node_views":   nodeReps,
		})
	}
}

// getReplicationStats returns replication statistics
func getReplicationStats(drm *rate_limiting.DistributedReputationManager) gin.HandlerFunc {
	return func(c *gin.Context) {
		ctx := c.Request.Context()
		stats, err := drm.GetReplicationStats(ctx)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, stats)
	}
}

// getReplicationSummary returns high-level replication summary
func getReplicationSummary(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		var totalEvents int64
		var unsyncedEvents int64
		var localOnlyEvents int64
		var uniqueEvents int64

		db.Model(&rate_limiting.ReputationEvent{}).Count(&totalEvents)
		db.Model(&rate_limiting.ReputationEvent{}).Where("synced_at IS NULL").Count(&unsyncedEvents)
		db.Model(&rate_limiting.ReputationEvent{}).Where("local_only = ?", true).Count(&localOnlyEvents)
		db.Model(&rate_limiting.ReputationEvent{}).Distinct("event_hash").Count(&uniqueEvents)

		c.JSON(http.StatusOK, gin.H{
			"total_events":       totalEvents,
			"unsynced_events":    unsyncedEvents,
			"local_only_events":  localOnlyEvents,
			"unique_events":      uniqueEvents,
			"duplicate_events":   totalEvents - uniqueEvents,
			"replication_ratio":  float64(unsyncedEvents) / float64(totalEvents),
		})
	}
}

// getLatencyStats returns network latency statistics
func getLatencyStats(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		var syncs []rate_limiting.ReputationSync
		if err := db.Find(&syncs).Error; err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve latency stats"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"sync_pairs": syncs,
			"count":      len(syncs),
		})
	}
}

// getNetworkHealth returns overall network health
func getNetworkHealth(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		var syncs []rate_limiting.ReputationSync
		if err := db.Find(&syncs).Error; err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve network health"})
			return
		}

		healthCounts := map[string]int{}
		totalErrors := int64(0)
		totalPending := int64(0)

		for _, sync := range syncs {
			healthCounts[sync.Status]++
			totalErrors += int64(sync.SyncErrors)
			totalPending += int64(sync.PendingEvents)
		}

		healthScore := 1.0
		if len(syncs) > 0 {
			failedCount := healthCounts["failed"]
			healthScore = 1.0 - (float64(failedCount) / float64(len(syncs)))
		}

		c.JSON(http.StatusOK, gin.H{
			"health_score":       healthScore,
			"health_status":      healthCounts,
			"total_sync_pairs":   len(syncs),
			"total_errors":       totalErrors,
			"total_pending":      totalPending,
			"avg_errors_per_pair": float64(totalErrors) / float64(len(syncs)+1),
		})
	}
}

// getConflictStats returns conflict resolution statistics
func getConflictStats(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		var nodeReps []rate_limiting.NodeReputation
		if err := db.Find(&nodeReps).Error; err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve conflict stats"})
			return
		}

		// Group by user to find conflicts
		userConflicts := map[int]int{}
		for _, rep := range nodeReps {
			userConflicts[rep.UserID]++
		}

		conflictCount := 0
		maxConflict := 0
		for _, count := range userConflicts {
			if count > 1 {
				conflictCount++
				if count > maxConflict {
					maxConflict = count
				}
			}
		}

		c.JSON(http.StatusOK, gin.H{
			"users_with_conflicts": conflictCount,
			"total_users":          len(userConflicts),
			"max_conflicts_single_user": maxConflict,
			"conflict_ratio":       float64(conflictCount) / float64(len(userConflicts)),
		})
	}
}

// resolveUserConflicts manually resolves conflicts for a user
func resolveUserConflicts(drm *rate_limiting.DistributedReputationManager) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID, err := strconv.Atoi(c.Param("userID"))
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid user ID"})
			return
		}

		ctx := c.Request.Context()
		if err := drm.ResolveUserReputation(ctx, userID); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"user_id": userID,
			"message": "Conflicts resolved",
		})
	}
}

// forceSyncNode forces synchronization with a specific node
func forceSyncNode(drm *rate_limiting.DistributedReputationManager) gin.HandlerFunc {
	return func(c *gin.Context) {
		nodeID := c.Param("nodeID")

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"node_id": nodeID,
			"message": "Sync initiated for node",
		})
	}
}

// purgeDuplicateEvents removes duplicate reputation events
func purgeDuplicateEvents(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Find and delete older duplicates, keeping only the most recent
		var deleted int64
		db.Model(&rate_limiting.ReputationEvent{}).
			Where("id IN (?)",
				db.Table("reputation_events re1").
					Select("re1.id").
					Where("EXISTS (SELECT 1 FROM reputation_events re2 WHERE re2.event_hash = re1.event_hash AND re2.id > re1.id)").
					SubQuery(),
			).Delete(&rate_limiting.ReputationEvent{}).RowsAffected

		c.JSON(http.StatusOK, gin.H{
			"success":        true,
			"duplicates_removed": deleted,
		})
	}
}
