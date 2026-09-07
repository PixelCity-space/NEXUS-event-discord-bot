-- Migration 002: Cascade Foreign Keys and JSONB Data Types Hardening
-- Enforces referential integrity with ON DELETE CASCADE and unifies emoji set JSONB storage

-- 1. Purge any historical orphaned records before applying constraints
DELETE FROM rsvps WHERE event_id NOT IN (SELECT event_id FROM active_events);
DELETE FROM event_reminders WHERE event_id NOT IN (SELECT event_id FROM active_events);

-- 2. Add Foreign Key Constraints with ON DELETE CASCADE (idempotent block)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_rsvps_active_events'
    ) THEN
        ALTER TABLE rsvps
            ADD CONSTRAINT fk_rsvps_active_events
            FOREIGN KEY (event_id)
            REFERENCES active_events(event_id)
            ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_event_reminders_active_events'
    ) THEN
        ALTER TABLE event_reminders
            ADD CONSTRAINT fk_event_reminders_active_events
            FOREIGN KEY (event_id)
            REFERENCES active_events(event_id)
            ON DELETE CASCADE;
    END IF;
END $$;

-- 3. Convert global_emoji_sets.data from TEXT to JSONB if needed
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'global_emoji_sets' 
          AND column_name = 'data' 
          AND data_type = 'text'
    ) THEN
        ALTER TABLE global_emoji_sets
            ALTER COLUMN data TYPE JSONB USING data::jsonb;
    END IF;
END $$;
