-- Migration 001: Initial Schema Definition
-- Creates all base tables, constraints, and indexes for Nexus Bot

-- 1. Active & Scheduled Events
CREATE TABLE IF NOT EXISTS active_events (
    event_id TEXT PRIMARY KEY,
    config_name TEXT,
    message_id BIGINT,
    channel_id BIGINT,
    start_time DOUBLE PRECISION,
    status TEXT DEFAULT 'active',
    title TEXT,
    description TEXT,
    image_urls TEXT,
    color TEXT,
    max_accepted INTEGER,
    ping_role BIGINT,
    end_time DOUBLE PRECISION,
    recurrence_type TEXT,
    repost_trigger TEXT,
    repost_offset TEXT,
    timezone TEXT DEFAULT 'Europe/Budapest',
    creator_id TEXT,
    reminder_type TEXT DEFAULT 'none',
    reminder_offset TEXT DEFAULT '15m',
    reminder_sent INTEGER DEFAULT 0,
    reminder_message TEXT,
    recurrence_limit INTEGER DEFAULT 0,
    recurrence_count INTEGER DEFAULT 0,
    icon_set TEXT DEFAULT 'standard',
    extra_data TEXT,
    guild_id TEXT,
    temp_role_id BIGINT,
    use_temp_role BOOLEAN DEFAULT FALSE,
    rsvp_allowed_role_ids TEXT DEFAULT '',
    lobby_mode BOOLEAN DEFAULT FALSE,
    lobby_expires_at DOUBLE PRECISION,
    lobby_remind_on_fill BOOLEAN DEFAULT TRUE
);

-- 2. RSVPs and Attendance
CREATE TABLE IF NOT EXISTS rsvps (
    event_id TEXT NOT NULL REFERENCES active_events(event_id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    status TEXT,
    joined_at DOUBLE PRECISION,
    attendance TEXT DEFAULT 'present',
    PRIMARY KEY (event_id, user_id)
);

-- 3. Event Drafts
CREATE TABLE IF NOT EXISTS event_drafts (
    draft_id TEXT PRIMARY KEY,
    creator_id TEXT,
    title TEXT,
    data JSONB,
    updated_at DOUBLE PRECISION,
    guild_id TEXT
);

-- 4. Guild-specific Custom Emoji Sets
CREATE TABLE IF NOT EXISTS guild_emoji_sets (
    guild_id TEXT NOT NULL,
    set_id TEXT NOT NULL,
    name TEXT,
    data JSONB,
    PRIMARY KEY (guild_id, set_id)
);

-- 5. Guild Translations / Overrides
CREATE TABLE IF NOT EXISTS guild_translations (
    guild_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    PRIMARY KEY (guild_id, key)
);

-- 6. Guild Settings
CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    PRIMARY KEY (guild_id, key)
);

-- 7. Global Bot Settings
CREATE TABLE IF NOT EXISTS global_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- 8. Event Reminders (Multi-slot)
CREATE TABLE IF NOT EXISTS event_reminders (
    event_id TEXT NOT NULL REFERENCES active_events(event_id) ON DELETE CASCADE,
    slot_idx SMALLINT NOT NULL,
    offset_str TEXT NOT NULL,
    method TEXT,
    custom_message TEXT,
    target TEXT DEFAULT 'coming',
    sent INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (event_id, slot_idx),
    CHECK (slot_idx >= 0 AND slot_idx < 5)
);

-- 9. Global Emoji Sets
CREATE TABLE IF NOT EXISTS global_emoji_sets (
    set_id TEXT PRIMARY KEY,
    name TEXT,
    data JSONB
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_active_events_guild_status ON active_events (guild_id, status);
CREATE INDEX IF NOT EXISTS idx_active_events_start_time ON active_events (start_time);
CREATE INDEX IF NOT EXISTS idx_rsvps_event_id ON rsvps (event_id);
CREATE INDEX IF NOT EXISTS idx_rsvps_user_id ON rsvps (user_id);
CREATE INDEX IF NOT EXISTS idx_event_reminders_event_id ON event_reminders (event_id);
CREATE INDEX IF NOT EXISTS idx_guild_settings_guild_id ON guild_settings (guild_id);
CREATE INDEX IF NOT EXISTS idx_guild_translations_guild_id ON guild_translations (guild_id);
CREATE INDEX IF NOT EXISTS idx_event_drafts_guild_creator ON event_drafts (guild_id, creator_id);
