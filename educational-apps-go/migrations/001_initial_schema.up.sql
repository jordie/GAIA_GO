-- Create users table (shared across all apps)
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE
);

-- Create sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- READING APP TABLES
CREATE TABLE IF NOT EXISTS reading_lessons (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    difficulty_level INT CHECK (difficulty_level >= 1 AND difficulty_level <= 5),
    content TEXT NOT NULL,
    audio_url VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reading_word_mastery (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    word VARCHAR(255) NOT NULL,
    proficiency_level INT CHECK (proficiency_level >= 0 AND proficiency_level <= 100),
    times_practiced INT DEFAULT 0,
    last_practiced TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, word)
);

CREATE TABLE IF NOT EXISTS reading_comprehension_answers (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson_id BIGINT NOT NULL REFERENCES reading_lessons(id) ON DELETE CASCADE,
    question_id INT NOT NULL,
    user_answer TEXT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    answered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- MATH APP TABLES
CREATE TABLE IF NOT EXISTS math_problems (
    id BIGSERIAL PRIMARY KEY,
    difficulty_level INT CHECK (difficulty_level >= 1 AND difficulty_level <= 5),
    problem_type VARCHAR(50) NOT NULL,
    operand1 INT NOT NULL,
    operand2 INT NOT NULL,
    operator VARCHAR(10) NOT NULL,
    correct_answer INT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS math_attempts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    problem_id BIGINT NOT NULL REFERENCES math_problems(id) ON DELETE CASCADE,
    user_answer INT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    response_time_ms INT,
    attempted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS math_progress (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    current_difficulty_level INT DEFAULT 1,
    total_problems_solved INT DEFAULT 0,
    accuracy_percentage DOUBLE PRECISION DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id)
);

-- PIANO APP TABLES
CREATE TABLE IF NOT EXISTS piano_notes (
    id BIGSERIAL PRIMARY KEY,
    note_name VARCHAR(10) NOT NULL UNIQUE,
    frequency_hz DOUBLE PRECISION NOT NULL,
    midi_number INT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS piano_exercises (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    difficulty_level INT CHECK (difficulty_level >= 1 AND difficulty_level <= 5),
    notes_sequence VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS piano_attempts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exercise_id BIGINT NOT NULL REFERENCES piano_exercises(id) ON DELETE CASCADE,
    notes_played VARCHAR(255) NOT NULL,
    is_correct BOOLEAN NOT NULL,
    accuracy_percentage DOUBLE PRECISION,
    response_time_ms INT,
    attempted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- TYPING APP TABLES
CREATE TABLE IF NOT EXISTS typing_exercises (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    text_content TEXT NOT NULL,
    difficulty_level INT CHECK (difficulty_level >= 1 AND difficulty_level <= 5),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS typing_attempts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exercise_id BIGINT NOT NULL REFERENCES typing_exercises(id) ON DELETE CASCADE,
    text_typed TEXT NOT NULL,
    accuracy_percentage DOUBLE PRECISION NOT NULL,
    wpm INT NOT NULL,
    duration_seconds INT NOT NULL,
    attempted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS typing_progress (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    average_wpm INT DEFAULT 0,
    average_accuracy DOUBLE PRECISION DEFAULT 0,
    total_exercises_completed INT DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id)
);

-- COMPREHENSION APP TABLES
CREATE TABLE IF NOT EXISTS comprehension_passages (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    difficulty_level INT CHECK (difficulty_level >= 1 AND difficulty_level <= 5),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS comprehension_questions (
    id BIGSERIAL PRIMARY KEY,
    passage_id BIGINT NOT NULL REFERENCES comprehension_passages(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    question_type VARCHAR(50) NOT NULL,
    correct_answer VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS comprehension_answers (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    question_id BIGINT NOT NULL REFERENCES comprehension_questions(id) ON DELETE CASCADE,
    user_answer VARCHAR(255) NOT NULL,
    is_correct BOOLEAN NOT NULL,
    answered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_reading_word_mastery_user_id ON reading_word_mastery(user_id);
CREATE INDEX IF NOT EXISTS idx_math_attempts_user_id ON math_attempts(user_id);
CREATE INDEX IF NOT EXISTS idx_math_progress_user_id ON math_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_piano_attempts_user_id ON piano_attempts(user_id);
CREATE INDEX IF NOT EXISTS idx_typing_attempts_user_id ON typing_attempts(user_id);
CREATE INDEX IF NOT EXISTS idx_typing_progress_user_id ON typing_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_comprehension_answers_user_id ON comprehension_answers(user_id);
