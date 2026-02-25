-- Add worker skills and task skill requirements for skill-based task assignment
-- Created: 2026-01-31

-- Worker skills/expertise tracking
CREATE TABLE IF NOT EXISTS worker_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    proficiency INTEGER DEFAULT 50,
    tasks_completed INTEGER DEFAULT 0,
    avg_duration_seconds REAL,
    last_used TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (worker_id) REFERENCES workers(id) ON DELETE CASCADE,
    UNIQUE(worker_id, skill_name)
);
CREATE INDEX IF NOT EXISTS idx_worker_skills_worker ON worker_skills(worker_id);
CREATE INDEX IF NOT EXISTS idx_worker_skills_skill ON worker_skills(skill_name);
CREATE INDEX IF NOT EXISTS idx_worker_skills_proficiency ON worker_skills(proficiency);

-- Task skill requirements
CREATE TABLE IF NOT EXISTS task_skill_requirements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    min_proficiency INTEGER DEFAULT 0,
    priority INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task_type, skill_name)
);
CREATE INDEX IF NOT EXISTS idx_task_skills_type ON task_skill_requirements(task_type);
CREATE INDEX IF NOT EXISTS idx_task_skills_skill ON task_skill_requirements(skill_name);

-- Insert default skill requirements for common task types
INSERT OR IGNORE INTO task_skill_requirements (task_type, skill_name, min_proficiency, priority) VALUES
    ('deploy', 'deployment', 60, 3),
    ('deploy', 'docker', 40, 2),
    ('deploy', 'kubernetes', 30, 1),
    ('test', 'testing', 50, 3),
    ('test', 'python', 30, 1),
    ('build', 'build_systems', 50, 3),
    ('build', 'docker', 40, 2),
    ('python', 'python', 60, 3),
    ('shell', 'bash', 50, 2),
    ('git', 'git', 50, 3),
    ('claude_task', 'ai_prompting', 40, 2),
    ('web_crawl', 'web_scraping', 50, 2),
    ('error_fix', 'debugging', 60, 3),
    ('error_fix', 'python', 40, 2);
