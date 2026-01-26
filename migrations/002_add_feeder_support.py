"""
Add support for automatic aquarium feeders
"""

steps = [
    # Create feeder table
    "CREATE TABLE feeder(id TEXT PRIMARY KEY, enclosure TEXT NOT NULL, name TEXT NOT NULL, hardware TEXT NOT NULL, enabled BOOLEAN DEFAULT 1, servo_config TEXT NOT NULL, schedule TEXT NOT NULL, notification BOOLEAN DEFAULT 1, FOREIGN KEY(enclosure) REFERENCES enclosure(id))",
    
    "CREATE TABLE feeder_history(feeder TEXT NOT NULL, timestamp TEXT NOT NULL, status TEXT NOT NULL, portion_size REAL DEFAULT 0, PRIMARY KEY(feeder, timestamp), FOREIGN KEY(feeder) REFERENCES feeder(id) ON DELETE CASCADE)",
    "CREATE INDEX idx_feeder_history_feeder ON feeder_history(feeder)",
]

def forward(backend):
    cursor = backend.cursor()
    for step in steps:
        cursor.execute(step)

def backward(backend):
    cursor = backend.cursor()
    cursor.execute("DROP TABLE IF EXISTS feeder_history")
    cursor.execute("DROP TABLE IF EXISTS feeder")