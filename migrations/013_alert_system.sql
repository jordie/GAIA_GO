-- Phase 11.4.3: Alert System Tables
--
-- Tables:
-- 1. alert_rules - Alert rule configuration
-- 2. alerts - Triggered alerts
-- 3. alert_notifications - Notification log

-- Alert rule configuration
CREATE TABLE IF NOT EXISTS alert_rules (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    alert_type VARCHAR(50),                  -- high_utilization, quota_violation, etc
    condition VARCHAR(255),                  -- Condition description
    threshold FLOAT DEFAULT 80.0,            -- Threshold value
    period VARCHAR(20),                      -- daily, hourly, realtime
    enabled BOOLEAN DEFAULT true,
    notification_channels TEXT[],            -- email, webhook, slack, dashboard
    notify_users BOOLEAN DEFAULT true,       -- Notify affected users
    notify_admins BOOLEAN DEFAULT true,      -- Notify admins
    severity VARCHAR(20),                    -- low, medium, high, critical
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for alert rules
CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled ON alert_rules(enabled);
CREATE INDEX IF NOT EXISTS idx_alert_rules_type ON alert_rules(alert_type);

-- Triggered alerts
CREATE TABLE IF NOT EXISTS alerts (
    id BIGSERIAL PRIMARY KEY,
    rule_id BIGINT,
    alert_type VARCHAR(50),                  -- Type of alert
    severity VARCHAR(20),                    -- low, medium, high, critical
    status VARCHAR(20),                      -- new, monitoring, resolved, muted
    user_id BIGINT,                          -- User affected (if applicable)
    username VARCHAR(255),                   -- Username for reference
    command_type VARCHAR(50),                -- Command type (if applicable)
    message TEXT,                            -- Alert message
    details JSONB,                           -- Additional details
    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_rule FOREIGN KEY (rule_id) REFERENCES alert_rules(id) ON DELETE CASCADE,
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- Create indexes for alerts
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_user ON alerts(user_id, triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_triggered ON alerts(triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_rule ON alerts(rule_id);

-- Alert notification log
CREATE TABLE IF NOT EXISTS alert_notifications (
    id BIGSERIAL PRIMARY KEY,
    alert_id BIGINT NOT NULL,
    channel VARCHAR(50),                     -- email, webhook, slack, dashboard
    recipient VARCHAR(255),                  -- Email address or webhook URL
    sent_at TIMESTAMP,                       -- When notification was sent
    status VARCHAR(20),                      -- pending, sent, failed
    error_msg TEXT,                          -- Error message if failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_alert FOREIGN KEY (alert_id) REFERENCES alerts(id) ON DELETE CASCADE
);

-- Create indexes for notifications
CREATE INDEX IF NOT EXISTS idx_notifications_alert ON alert_notifications(alert_id);
CREATE INDEX IF NOT EXISTS idx_notifications_channel ON alert_notifications(channel);
CREATE INDEX IF NOT EXISTS idx_notifications_status ON alert_notifications(status);

-- Insert default alert rules
INSERT INTO alert_rules (name, description, alert_type, condition, threshold, period, severity, notification_channels, enabled)
VALUES
    ('High Daily Quota Utilization', 'Alert when user daily quota exceeds 80%', 'high_utilization', 'usage > 80', 80.0, 'daily', 'high', ARRAY['email', 'dashboard'], true),
    ('Approaching Daily Limit', 'Alert when user daily quota exceeds 90%', 'approaching_limit', 'usage > 90', 90.0, 'daily', 'high', ARRAY['email', 'dashboard'], true),
    ('Quota Violations', 'Alert when quota violations exceed threshold', 'quota_violation', 'violations > 5', 5.0, 'daily', 'critical', ARRAY['email', 'slack', 'dashboard'], true),
    ('Sustained Throttling', 'Alert when system sustained throttling detected', 'sustained_throttling', 'throttle_factor < 0.5', 50.0, 'realtime', 'high', ARRAY['slack', 'dashboard'], true),
    ('High System Load', 'Alert when CPU or memory exceeds 85%', 'high_system_load', 'cpu > 85 OR memory > 85', 85.0, 'realtime', 'critical', ARRAY['slack', 'dashboard'], true)
ON CONFLICT DO NOTHING;

-- Create view for active alerts
CREATE OR REPLACE VIEW active_alerts AS
SELECT
    a.id,
    a.alert_type,
    a.severity,
    a.status,
    a.user_id,
    a.username,
    a.message,
    a.triggered_at,
    ar.name as rule_name,
    COUNT(an.id) as notification_count
FROM alerts a
LEFT JOIN alert_rules ar ON a.rule_id = ar.id
LEFT JOIN alert_notifications an ON a.id = an.alert_id
WHERE a.status IN ('new', 'monitoring')
GROUP BY a.id, ar.name;

-- Create view for alert statistics
CREATE OR REPLACE VIEW alert_statistics AS
SELECT
    DATE(a.triggered_at) as date,
    a.alert_type,
    a.severity,
    COUNT(*) as total_alerts,
    COUNT(DISTINCT a.user_id) as affected_users,
    COUNT(CASE WHEN a.status = 'resolved' THEN 1 END) as resolved,
    COUNT(CASE WHEN a.status IN ('new', 'monitoring') THEN 1 END) as active
FROM alerts a
WHERE a.triggered_at > NOW() - INTERVAL '30 days'
GROUP BY DATE(a.triggered_at), a.alert_type, a.severity
ORDER BY date DESC;
