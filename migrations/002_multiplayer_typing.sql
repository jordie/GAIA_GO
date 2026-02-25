-- TARGET: all
-- Phase 10: Multiplayer Typing System
-- Adds support for real-time multiplayer racing

-- ============================================================================
-- RACE ROOMS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS race_rooms (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    host_user_id INTEGER NOT NULL,
    race_text TEXT NOT NULL,
    word_count INTEGER DEFAULT 30,
    difficulty TEXT DEFAULT 'medium',
    max_players INTEGER DEFAULT 4,
    min_players INTEGER DEFAULT 2,
    state TEXT DEFAULT 'waiting',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    FOREIGN KEY (host_user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_race_rooms_host_user_id ON race_rooms(host_user_id);
CREATE INDEX IF NOT EXISTS idx_race_rooms_state ON race_rooms(state);
CREATE INDEX IF NOT EXISTS idx_race_rooms_created_at ON race_rooms(created_at);

-- ============================================================================
-- RACE PARTICIPANTS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS race_participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id TEXT NOT NULL,
    user_id INTEGER,
    participant_type TEXT DEFAULT 'human',
    username TEXT NOT NULL,
    placement INTEGER,
    wpm INTEGER,
    accuracy REAL,
    race_time REAL,
    finished_at TIMESTAMP,
    xp_earned INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (race_id) REFERENCES race_rooms(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_race_participants_race_id ON race_participants(race_id);
CREATE INDEX IF NOT EXISTS idx_race_participants_user_id ON race_participants(user_id);
CREATE INDEX IF NOT EXISTS idx_race_participants_placement ON race_participants(placement);

-- ============================================================================
-- EXTEND EXISTING RACING_STATS TABLE
-- ============================================================================

ALTER TABLE racing_stats ADD COLUMN multiplayer_races INTEGER DEFAULT 0;
ALTER TABLE racing_stats ADD COLUMN multiplayer_wins INTEGER DEFAULT 0;
ALTER TABLE racing_stats ADD COLUMN multiplayer_podiums INTEGER DEFAULT 0;

-- ============================================================================
-- EXTEND EXISTING RACES TABLE
-- ============================================================================

ALTER TABLE races ADD COLUMN race_id TEXT;
ALTER TABLE races ADD COLUMN race_type TEXT DEFAULT 'ai';

CREATE INDEX IF NOT EXISTS idx_races_race_type ON races(race_type);
