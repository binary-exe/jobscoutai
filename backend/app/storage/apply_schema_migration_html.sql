-- Migration: Add HTML storage to job_targets table
-- Run this in Supabase SQL Editor after running apply_schema.sql

ALTER TABLE job_targets 
ADD COLUMN IF NOT EXISTS html TEXT;

-- Add comment
COMMENT ON COLUMN job_targets.html IS 'Stored HTML content from job page fetch (for trust report regeneration)';
