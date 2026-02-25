-- Migration: Add crawl results storage
-- Created: 2026-02-10
-- Task: P06 - Add Crawl Results Storage

-- Crawl Results table for storing web crawler task results
CREATE TABLE IF NOT EXISTS crawl_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    prompt TEXT NOT NULL,
    start_url TEXT,
    final_url TEXT,
    success BOOLEAN DEFAULT 0,
    extracted_data TEXT,  -- JSON
    action_history TEXT,  -- JSON
    screenshots TEXT,     -- JSON array of screenshot paths
    error_message TEXT,
    duration_seconds REAL,
    llm_provider TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_crawl_results_task_id ON crawl_results(task_id);
CREATE INDEX IF NOT EXISTS idx_crawl_results_created_at ON crawl_results(created_at);
CREATE INDEX IF NOT EXISTS idx_crawl_results_success ON crawl_results(success);
CREATE INDEX IF NOT EXISTS idx_crawl_results_llm_provider ON crawl_results(llm_provider);
