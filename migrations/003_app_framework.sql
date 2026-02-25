-- TARGET: all
-- Phase 11: App Framework Infrastructure
-- Shared services for all GAIA apps

-- ============================================================================
-- APP STATS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS app_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    app_name TEXT NOT NULL,
    stat_name TEXT NOT NULL,
    value INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, app_name, stat_name)
);

CREATE INDEX IF NOT EXISTS idx_app_stats_user_app ON app_stats(user_id, app_name);

-- ============================================================================
-- APP SCORES TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS app_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    app_name TEXT NOT NULL,
    score INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_app_scores_user_app ON app_scores(user_id, app_name);
CREATE INDEX IF NOT EXISTS idx_app_scores_app_score ON app_scores(app_name, score DESC);

-- ============================================================================
-- ACHIEVEMENTS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS achievements (
    id TEXT PRIMARY KEY,
    app_name TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    icon TEXT,
    points INTEGER DEFAULT 0,
    threshold INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_achievements_app_name ON achievements(app_name);

-- ============================================================================
-- USER ACHIEVEMENTS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_achievements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    achievement_id TEXT NOT NULL,
    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (achievement_id) REFERENCES achievements(id),
    UNIQUE(user_id, achievement_id)
);

CREATE INDEX IF NOT EXISTS idx_user_achievements_user ON user_achievements(user_id);
CREATE INDEX IF NOT EXISTS idx_user_achievements_achievement ON user_achievements(achievement_id);

-- ============================================================================
-- APP PROGRESS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS app_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    app_name TEXT NOT NULL,
    level INTEGER DEFAULT 1,
    experience INTEGER DEFAULT 0,
    streak INTEGER DEFAULT 0,
    last_played TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, app_name)
);

CREATE INDEX IF NOT EXISTS idx_app_progress_user_app ON app_progress(user_id, app_name);
