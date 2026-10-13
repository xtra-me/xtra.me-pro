-- =============================================
-- xtra.me-pro — Phase 2 Migration
-- Run in Supabase SQL Editor
-- Date: 2026-10-13
-- =============================================

-- 1. Add new columns to projects table
ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS current_phase INTEGER NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS video_type TEXT,
  ADD COLUMN IF NOT EXISTS target_audience TEXT,
  ADD COLUMN IF NOT EXISTS requirements TEXT;

-- 2. Add YouTube-specific fields to idea_pitches
ALTER TABLE idea_pitches
  ADD COLUMN IF NOT EXISTS video_type TEXT,
  ADD COLUMN IF NOT EXISTS target_audience TEXT,
  ADD COLUMN IF NOT EXISTS requirements TEXT,
  ADD COLUMN IF NOT EXISTS target_start_date DATE,
  ADD COLUMN IF NOT EXISTS target_end_date DATE;

-- 3. Add last_seen to org_members (if not already exists — used by email_job)
ALTER TABLE org_members
  ADD COLUMN IF NOT EXISTS last_seen TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS work_schedule TEXT,
  ADD COLUMN IF NOT EXISTS timezone TEXT,
  ADD COLUMN IF NOT EXISTS groq_api_key TEXT;

-- 4. Verify
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name IN ('projects', 'idea_pitches', 'org_members')
ORDER BY table_name, column_name;
