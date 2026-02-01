"""
Add monitoring zones and events tables
"""

steps = [
    "CREATE TABLE IF NOT EXISTS \"MonitoringZone\" (\"id\" TEXT NOT NULL, \"enclosure\" TEXT NOT NULL, \"name\" TEXT NOT NULL, \"type\" TEXT NOT NULL, \"shape\" JSON NOT NULL, \"meta\" JSON NOT NULL, \"enabled\" BOOLEAN DEFAULT 1, FOREIGN KEY(\"enclosure\") REFERENCES \"Enclosure\"(\"id\") ON DELETE CASCADE, PRIMARY KEY(\"id\"))",
    "CREATE TABLE IF NOT EXISTS \"MonitoringEvent\" (\"id\" TEXT NOT NULL, \"enclosure\" TEXT NOT NULL, \"zone\" TEXT, \"timestamp\" TEXT NOT NULL, \"label\" TEXT, \"confidence\" REAL, \"source\" TEXT, \"snapshot\" TEXT, \"meta\" JSON NOT NULL, FOREIGN KEY(\"enclosure\") REFERENCES \"Enclosure\"(\"id\") ON DELETE CASCADE, FOREIGN KEY(\"zone\") REFERENCES \"MonitoringZone\"(\"id\") ON DELETE SET NULL, PRIMARY KEY(\"id\"))",
    "CREATE INDEX IF NOT EXISTS \"idx_monitoring_event_enclosure\" ON \"MonitoringEvent\" (\"enclosure\")",
    "CREATE INDEX IF NOT EXISTS \"idx_monitoring_event_zone\" ON \"MonitoringEvent\" (\"zone\")",
    "CREATE INDEX IF NOT EXISTS \"idx_monitoring_event_timestamp\" ON \"MonitoringEvent\" (\"timestamp\")",
]


def forward(backend):
    cursor = backend.cursor()
    for step in steps:
        cursor.execute(step)


def backward(backend):
    cursor = backend.cursor()
    cursor.execute("DROP TABLE IF EXISTS \"MonitoringEvent\"")
    cursor.execute("DROP TABLE IF EXISTS \"MonitoringZone\"")
