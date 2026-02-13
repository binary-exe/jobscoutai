-- Migration: Recruiter/contact fields on applications (Phase 2 tracker)
-- Additive, nullable. Run after apply_schema.sql.

ALTER TABLE applications ADD COLUMN IF NOT EXISTS contact_email TEXT;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS contact_linkedin_url TEXT;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS contact_phone TEXT;
