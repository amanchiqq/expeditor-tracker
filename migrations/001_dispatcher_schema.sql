-- Existing timestamp-without-time-zone values are interpreted as UTC.
-- Back up existing databases and confirm this assumption before migration.
CREATE TABLE IF NOT EXISTS users (
    username VARCHAR(50) PRIMARY KEY,
    password VARCHAR(255) NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    expeditor_id INTEGER NOT NULL,
    description VARCHAR(255),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'in_progress',
    eta TIMESTAMPTZ
);
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'in_progress';
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS eta TIMESTAMPTZ;
ALTER TABLE tasks ALTER COLUMN latitude DROP NOT NULL;
ALTER TABLE tasks ALTER COLUMN longitude DROP NOT NULL;
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='tasks' AND column_name='created_at' AND data_type='timestamp without time zone') THEN
        ALTER TABLE tasks ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='tasks' AND column_name='eta' AND data_type='timestamp without time zone') THEN
        ALTER TABLE tasks ALTER COLUMN eta TYPE TIMESTAMPTZ USING eta AT TIME ZONE 'UTC';
    END IF;
END $$;
UPDATE tasks SET status='in_progress' WHERE status IS NULL;
ALTER TABLE tasks ALTER COLUMN status SET DEFAULT 'in_progress';
ALTER TABLE tasks ALTER COLUMN status SET NOT NULL;
ALTER TABLE tasks ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE tasks ADD CONSTRAINT tasks_expeditor_positive CHECK (expeditor_id>0);
ALTER TABLE tasks ADD CONSTRAINT tasks_status_valid CHECK (status IN ('in_progress','completed'));
ALTER TABLE tasks ADD CONSTRAINT tasks_coordinates_valid CHECK (
    (latitude IS NULL AND longitude IS NULL) OR
    (latitude IS NOT NULL AND longitude IS NOT NULL AND latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)
);
CREATE INDEX IF NOT EXISTS tasks_expeditor_id_idx ON tasks(expeditor_id);
CREATE INDEX IF NOT EXISTS tasks_created_at_idx ON tasks(created_at);
