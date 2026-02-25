-- Migration 007: Add extended fields to bugs table
-- Adds screenshot, context, and category columns for enhanced bug tracking

-- Add screenshot column (base64 encoded image or URL)
ALTER TABLE bugs ADD COLUMN screenshot TEXT;

-- Add context column (JSON with additional context like browser, OS, user actions)
ALTER TABLE bugs ADD COLUMN context TEXT;

-- Add category column (e.g., 'ui', 'api', 'performance', 'security')
ALTER TABLE bugs ADD COLUMN category TEXT;
