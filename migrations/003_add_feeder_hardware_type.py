"""
Add hardware_type field to feeder table for ESP32 WiFi feeder support
"""

from yoyo import step

__depends__ = {'002_add_feeder_support'}

steps = [
    step(
        "ALTER TABLE feeder ADD COLUMN hardware_type TEXT DEFAULT 'gpio'",
        "ALTER TABLE feeder DROP COLUMN hardware_type"
    )
]
