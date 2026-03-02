package rate_limiting

import (
	"context"
	"encoding/json"
	"time"

	"gorm.io/datatypes"
	"gorm.io/gorm"
)

// MessageType represents the type of negotiation message
type MessageType string

const (
	MessageTypeMessage      MessageType = "message"
	MessageTypeQuestion     MessageType = "question"
	MessageTypeClarification MessageType = "clarification"
	MessageTypeProposal     MessageType = "proposal"
)

// SenderType represents who sent the message
type SenderType string

const (
	SenderTypeUser  SenderType = "user"
	SenderTypeAdmin SenderType = "admin"
)

// NegotiationMessage represents a single message in appeal negotiation
type NegotiationMessage struct {
	ID            int64
	AppealID      int
	SenderID      int
	SenderType    SenderType
	Message       string
	MessageType   MessageType
	Metadata      datatypes.JSONMap
	AttachmentURLs []string
	SentimentScore *float64
	LanguageScore  *float64
	IsPinned      bool
	CreatedAt     time.Time
	UpdatedAt     time.Time
}

// NegotiationThread represents the complete negotiation conversation
type NegotiationThread struct {
	AppealID      int                    `json:"appeal_id"`
	Messages      []NegotiationMessage   `json:"messages"`
	MessageCount  int                    `json:"message_count"`
	UserMessages  int                    `json:"user_messages"`
	AdminMessages int                    `json:"admin_messages"`
	LastUpdate    time.Time              `json:"last_update"`
	AvgSentiment  *float64               `json:"avg_sentiment"`
	AvgQuality    *float64               `json:"avg_quality"`
}

// AppealNegotiationService manages appeal negotiation messages
type AppealNegotiationService struct {
	db *gorm.DB
}

// NewAppealNegotiationService creates a new negotiation service
func NewAppealNegotiationService(db *gorm.DB) *AppealNegotiationService {
	return &AppealNegotiationService{db: db}
}

// SendMessage sends a negotiation message
func (ans *AppealNegotiationService) SendMessage(
	ctx context.Context,
	appealID int,
	senderID int,
	senderType SenderType,
	message string,
	messageType MessageType,
	metadata map[string]interface{},
	attachmentURLs []string,
) (*NegotiationMessage, error) {
	// Convert metadata to JSON
	jsonMetadata := datatypes.JSONMap{}
	if metadata != nil {
		data, _ := json.Marshal(metadata)
		json.Unmarshal(data, &jsonMetadata)
	}

	negotiationMsg := NegotiationMessage{
		AppealID:       appealID,
		SenderID:       senderID,
		SenderType:     senderType,
		Message:        message,
		MessageType:    messageType,
		Metadata:       jsonMetadata,
		AttachmentURLs: attachmentURLs,
		CreatedAt:      time.Now(),
		UpdatedAt:      time.Now(),
	}

	result := ans.db.WithContext(ctx).
		Table("appeal_negotiation_messages").
		Create(&negotiationMsg)

	if result.Error != nil {
		return nil, result.Error
	}

	// Update appeal status if not already reviewing
	ans.db.WithContext(ctx).
		Table("appeals").
		Where("id = ? AND status = ?", appealID, AppealPending).
		Update("status", AppealReviewing)

	return &negotiationMsg, nil
}

// GetNegotiationThread returns all messages for an appeal
func (ans *AppealNegotiationService) GetNegotiationThread(
	ctx context.Context,
	appealID int,
) (*NegotiationThread, error) {
	var messages []NegotiationMessage

	result := ans.db.WithContext(ctx).
		Table("appeal_negotiation_messages").
		Where("appeal_id = ?", appealID).
		Order("created_at ASC").
		Scan(&messages)

	if result.Error != nil {
		return nil, result.Error
	}

	// Count message types
	userMsgCount := 0
	adminMsgCount := 0
	var avgSentiment, avgQuality float64
	sentimentCount := 0
	qualityCount := 0

	for _, msg := range messages {
		if msg.SenderType == SenderTypeUser {
			userMsgCount++
		} else {
			adminMsgCount++
		}

		if msg.SentimentScore != nil {
			avgSentiment += *msg.SentimentScore
			sentimentCount++
		}

		if msg.LanguageScore != nil {
			avgQuality += *msg.LanguageScore
			qualityCount++
		}
	}

	var lastUpdate time.Time
	if len(messages) > 0 {
		lastUpdate = messages[len(messages)-1].CreatedAt
	}

	var avgSentPtr, avgQualPtr *float64
	if sentimentCount > 0 {
		s := avgSentiment / float64(sentimentCount)
		avgSentPtr = &s
	}
	if qualityCount > 0 {
		q := avgQuality / float64(qualityCount)
		avgQualPtr = &q
	}

	thread := &NegotiationThread{
		AppealID:      appealID,
		Messages:      messages,
		MessageCount:  len(messages),
		UserMessages:  userMsgCount,
		AdminMessages: adminMsgCount,
		LastUpdate:    lastUpdate,
		AvgSentiment:  avgSentPtr,
		AvgQuality:    avgQualPtr,
	}

	return thread, nil
}

// GetUserConversations returns all conversations for a user
func (ans *AppealNegotiationService) GetUserConversations(
	ctx context.Context,
	userID int,
	limit int,
	offset int,
) ([]NegotiationThread, error) {
	// Get appeals for this user
	var appealIDs []int
	ans.db.WithContext(ctx).
		Table("appeals").
		Where("user_id = ?", userID).
		Where("id IN (SELECT DISTINCT appeal_id FROM appeal_negotiation_messages)").
		Order("created_at DESC").
		Limit(limit).
		Offset(offset).
		Pluck("id", &appealIDs)

	threads := make([]NegotiationThread, 0, len(appealIDs))
	for _, appealID := range appealIDs {
		thread, err := ans.GetNegotiationThread(ctx, appealID)
		if err == nil && thread != nil {
			threads = append(threads, *thread)
		}
	}

	return threads, nil
}

// GetAdminConversations returns appeals being negotiated
func (ans *AppealNegotiationService) GetAdminConversations(
	ctx context.Context,
	limit int,
	offset int,
) ([]NegotiationThread, error) {
	// Get appeals with recent negotiation activity
	var appealIDs []int
	ans.db.WithContext(ctx).
		Table("appeal_negotiation_messages").
		Select("DISTINCT appeal_id").
		Where("created_at > ?", time.Now().AddDate(0, 0, -7)).
		Order("MAX(created_at) DESC").
		Limit(limit).
		Offset(offset).
		Group("appeal_id").
		Pluck("appeal_id", &appealIDs)

	threads := make([]NegotiationThread, 0, len(appealIDs))
	for _, appealID := range appealIDs {
		thread, err := ans.GetNegotiationThread(ctx, appealID)
		if err == nil && thread != nil {
			threads = append(threads, *thread)
		}
	}

	return threads, nil
}

// PinMessage pins a message for importance
func (ans *AppealNegotiationService) PinMessage(
	ctx context.Context,
	messageID int64,
) error {
	return ans.db.WithContext(ctx).
		Table("appeal_negotiation_messages").
		Where("id = ?", messageID).
		Update("is_pinned", true).Error
}

// UnpinMessage unpins a message
func (ans *AppealNegotiationService) UnpinMessage(
	ctx context.Context,
	messageID int64,
) error {
	return ans.db.WithContext(ctx).
		Table("appeal_negotiation_messages").
		Where("id = ?", messageID).
		Update("is_pinned", false).Error
}

// GetPinnedMessages returns pinned messages for an appeal
func (ans *AppealNegotiationService) GetPinnedMessages(
	ctx context.Context,
	appealID int,
) ([]NegotiationMessage, error) {
	var messages []NegotiationMessage

	result := ans.db.WithContext(ctx).
		Table("appeal_negotiation_messages").
		Where("appeal_id = ? AND is_pinned = ?", appealID, true).
		Order("created_at DESC").
		Scan(&messages)

	return messages, result.Error
}

// AnalyzeConversationTone analyzes sentiment of messages
func (ans *AppealNegotiationService) AnalyzeConversationTone(
	ctx context.Context,
	appealID int,
) (map[string]interface{}, error) {
	thread, err := ans.GetNegotiationThread(ctx, appealID)
	if err != nil {
		return nil, err
	}

	// Analyze sentiment by sender
	userSentiments := make([]float64, 0)
	adminSentiments := make([]float64, 0)

	for _, msg := range thread.Messages {
		if msg.SentimentScore != nil {
			if msg.SenderType == SenderTypeUser {
				userSentiments = append(userSentiments, *msg.SentimentScore)
			} else {
				adminSentiments = append(adminSentiments, *msg.SentimentScore)
			}
		}
	}

	analysis := map[string]interface{}{
		"user_sentiment":      calculateAverage(userSentiments),
		"admin_sentiment":     calculateAverage(adminSentiments),
		"overall_sentiment":   thread.AvgSentiment,
		"conversation_health": determineConversationHealth(thread),
		"tone_trend":          analyzeToneTrend(thread.Messages),
	}

	return analysis, nil
}

// GetNegotiationMetrics returns negotiation statistics
func (ans *AppealNegotiationService) GetNegotiationMetrics(
	ctx context.Context,
) (map[string]interface{}, error) {
	var metrics struct {
		TotalNegotiations   int64
		AvgMessagesPerAppeal float64
		AvgResolutionTime    float64
		AvgUserMessages      float64
		AvgAdminMessages     float64
		AvgSentiment         float64
		AvgQuality           float64
	}

	// Total negotiation appeals
	ans.db.WithContext(ctx).
		Table("appeal_negotiation_messages").
		Select("COUNT(DISTINCT appeal_id)").
		Scan(&metrics.TotalNegotiations)

	// Average messages per appeal
	ans.db.WithContext(ctx).
		Table("appeal_negotiation_messages").
		Select("AVG(msg_count)").
		Where("msg_count > 0").
		Scan(&metrics.AvgMessagesPerAppeal)

	// Average sentiment and quality
	ans.db.WithContext(ctx).
		Table("appeal_negotiation_messages").
		Select("AVG(sentiment_score), AVG(language_score)").
		Scan(&struct {
			Sentiment float64
			Quality   float64
		}{metrics.AvgSentiment, metrics.AvgQuality})

	return map[string]interface{}{
		"total_negotiations":    metrics.TotalNegotiations,
		"avg_messages_per_appeal": metrics.AvgMessagesPerAppeal,
		"avg_user_messages":     metrics.AvgUserMessages,
		"avg_admin_messages":    metrics.AvgAdminMessages,
		"avg_sentiment":         metrics.AvgSentiment,
		"avg_quality":           metrics.AvgQuality,
	}, nil
}

// determineConversationHealth assesses negotiation health
func determineConversationHealth(thread *NegotiationThread) string {
	if thread.AvgSentiment == nil {
		return "unknown"
	}

	sentiment := *thread.AvgSentiment
	if sentiment > 0.3 {
		return "positive"
	} else if sentiment < -0.3 {
		return "negative"
	}
	return "neutral"
}

// analyzeToneTrend analyzes how tone changes over time
func analyzeToneTrend(messages []NegotiationMessage) string {
	if len(messages) < 2 {
		return "insufficient_data"
	}

	// Compare first half to second half
	midpoint := len(messages) / 2
	var firstHalfSent, secondHalfSent float64
	firstCount, secondCount := 0, 0

	for i := 0; i < midpoint; i++ {
		if messages[i].SentimentScore != nil {
			firstHalfSent += *messages[i].SentimentScore
			firstCount++
		}
	}

	for i := midpoint; i < len(messages); i++ {
		if messages[i].SentimentScore != nil {
			secondHalfSent += *messages[i].SentimentScore
			secondCount++
		}
	}

	if firstCount == 0 || secondCount == 0 {
		return "insufficient_data"
	}

	firstAvg := firstHalfSent / float64(firstCount)
	secondAvg := secondHalfSent / float64(secondCount)
	change := secondAvg - firstAvg

	if change > 0.2 {
		return "improving"
	} else if change < -0.2 {
		return "deteriorating"
	}
	return "stable"
}

// NOTE: datatypes.JSONMap already implements sql.Scanner interface
// Defining methods on external types is not allowed in Go
