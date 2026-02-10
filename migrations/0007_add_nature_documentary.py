"""Add tables for Nature Documentary clips and events"""

steps = [
    """
    CREATE TABLE IF NOT EXISTS "NatureDocEvent" (
        "id" TEXT NOT NULL PRIMARY KEY,
        "enclosure" TEXT,
        "camera_id" TEXT NOT NULL,
        "timestamp" TEXT NOT NULL,
        "confidence" REAL,
        "track_id" TEXT,
        "bbox" JSON NOT NULL DEFAULT '{}',
        "meta" JSON NOT NULL DEFAULT '{}',
        "status" TEXT NOT NULL DEFAULT 'queued',
        FOREIGN KEY("enclosure") REFERENCES "Enclosure"("id") ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "NatureDocClip" (
        "id" TEXT NOT NULL PRIMARY KEY,
        "event" TEXT NOT NULL,
        "enclosure" TEXT,
        "camera_id" TEXT NOT NULL,
        "created" TEXT NOT NULL,
        "start_time" TEXT NOT NULL,
        "end_time" TEXT NOT NULL,
        "duration" REAL NOT NULL,
        "confidence" REAL,
        "filepath" TEXT NOT NULL,
        "preview_path" TEXT,
        "metadata" JSON NOT NULL DEFAULT '{}',
        "score" REAL DEFAULT 0,
        "favorite" BOOLEAN DEFAULT 0,
        "status" TEXT NOT NULL DEFAULT 'ready',
        FOREIGN KEY("event") REFERENCES "NatureDocEvent"("id") ON DELETE CASCADE,
        FOREIGN KEY("enclosure") REFERENCES "Enclosure"("id") ON DELETE SET NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_nature_doc_event_camera ON "NatureDocEvent" ("camera_id")",
    "CREATE INDEX IF NOT EXISTS idx_nature_doc_event_timestamp ON "NatureDocEvent" ("timestamp")",
    "CREATE INDEX IF NOT EXISTS idx_nature_doc_clip_camera ON "NatureDocClip" ("camera_id")",
    "CREATE INDEX IF NOT EXISTS idx_nature_doc_clip_created ON "NatureDocClip" ("created")",
]


def forward(backend):
    cursor = backend.cursor()
    for step in steps:
        cursor.execute(step)


def backward(backend):
    cursor = backend.cursor()
    cursor.execute('DROP TABLE IF EXISTS "NatureDocClip"')
    cursor.execute('DROP TABLE IF EXISTS "NatureDocEvent"')
