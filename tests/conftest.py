import logging
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# terrariumLogging configures the live log files and turns warnings into user notifications on import.
# Tests use plain logging instead.
terrariumLogging = types.ModuleType("terrariumLogging")
terrariumLogging.logging = logging
sys.modules.setdefault("terrariumLogging", terrariumLogging)
