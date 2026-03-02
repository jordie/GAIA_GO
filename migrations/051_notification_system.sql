-- Phase 2 Sprint 2: Notification System Migration

-- Notifications Table
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    type VARCHAR(50) NOT NULL,
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    old_value VARCHAR(100),
    new_value VARCHAR(100),
    read BOOLEAN NOT NULL DEFAULT false,
    sent_at TIMESTAMP WITH TIME ZONE NOT NULL,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Notification Preferences Table
CREATE TABLE IF NOT EXISTS notification_preferences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    enable_tier_notifications BOOLEAN NOT NULL DEFAULT true,
    enable_violation_alerts BOOLEAN NOT NULL DEFAULT true,
    enable_vip_notifications BOOLEAN NOT NULL DEFAULT true,
    preferred_channels TEXT NOT NULL DEFAULT '["in_app","email"]',
    notify_on_violation BOOLEAN NOT NULL DEFAULT false,
    notify_on_decay BOOLEAN NOT NULL DEFAULT false,
    aggregate_daily BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Notification Delivery Log (for tracking sent notifications)
CREATE TABLE IF NOT EXISTS notification_deliveries (
    id SERIAL PRIMARY KEY,
    notification_id INTEGER NOT NULL,
    channel VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, sent, failed, bounced
    attempts INTEGER NOT NULL DEFAULT 0,
    last_attempt TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (notification_id) REFERENCES notifications(id) ON DELETE CASCADE
);

-- Indexes for Performance
CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_type ON notifications(type);
CREATE INDEX idx_notifications_user_read ON notifications(user_id, read);
CREATE INDEX idx_notifications_created_at ON notifications(created_at DESC);
CREATE INDEX idx_notifications_user_created ON notifications(user_id, created_at DESC);
CREATE INDEX idx_notification_preferences_user_id ON notification_preferences(user_id);
CREATE INDEX idx_notification_deliveries_notification_id ON notification_deliveries(notification_id);
CREATE INDEX idx_notification_deliveries_channel ON notification_deliveries(channel);
CREATE INDEX idx_notification_deliveries_status ON notification_deliveries(status);

-- View for Notification Summary
CREATE VIEW notification_summary AS
SELECT
    user_id,
    COUNT(*) as total_notifications,
    SUM(CASE WHEN read = false THEN 1 ELSE 0 END) as unread_count,
    SUM(CASE WHEN type = 'tier_change' THEN 1 ELSE 0 END) as tier_changes,
    SUM(CASE WHEN type = 'violation' THEN 1 ELSE 0 END) as violations,
    SUM(CASE WHEN type IN ('vip_assigned', 'vip_expiring', 'vip_expired') THEN 1 ELSE 0 END) as vip_events,
    SUM(CASE WHEN type = 'flagged' THEN 1 ELSE 0 END) as flagged_count,
    SUM(CASE WHEN type = 'trusted' THEN 1 ELSE 0 END) as trusted_count,
    MAX(created_at) as last_notification
FROM notifications
GROUP BY user_id;

-- View for Unread Notifications
CREATE VIEW unread_notifications AS
SELECT
    user_id,
    type,
    title,
    message,
    created_at,
    sent_at
FROM notifications
WHERE read = false
ORDER BY created_at DESC;

-- View for Pending Deliveries
CREATE VIEW pending_deliveries AS
SELECT
    n.id as notification_id,
    n.user_id,
    n.type,
    nd.channel,
    nd.attempts,
    nd.last_attempt,
    nd.error_message
FROM notifications n
JOIN notification_deliveries nd ON n.id = nd.notification_id
WHERE nd.status = 'pending' OR (nd.status = 'failed' AND nd.attempts < 3)
ORDER BY nd.last_attempt ASC NULLS FIRST;
