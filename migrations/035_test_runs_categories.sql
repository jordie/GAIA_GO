-- Migration 008: Add category and coverage columns to test_runs
-- Task #23: Enhanced Testing panel with test categories

-- Add category column (comma-separated list of test categories)
ALTER TABLE test_runs ADD COLUMN category TEXT DEFAULT 'all';

-- Add coverage percentage column
ALTER TABLE test_runs ADD COLUMN coverage INTEGER DEFAULT 0;

-- Create index for category filtering
CREATE INDEX IF NOT EXISTS idx_test_runs_category ON test_runs(category);
