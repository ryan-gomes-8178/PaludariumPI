# -*- coding: utf-8 -*-
import terrariumLogging

logger = terrariumLogging.logging.getLogger(__name__)

from . import terrariumWebcam
from io import BytesIO

from pathlib import Path
import subprocess


class terrariumRPIWebcam(terrariumWebcam):
    HARDWARE = "rpicam"
    NAME = "Raspberry PI camera"
    VALID_SOURCE = r"^rpicam$"
    INFO_SOURCE = "rpicam"

    def _load_hardware(self):
        # Prefer legacy raspistill, fallback to rpicam-still or libcamera-still
        candidates = [
            Path("/usr/bin/raspistill"),
            Path("/usr/bin/rpicam-still"),
            Path("/usr/bin/libcamera-still"),
        ]
        for path in candidates:
            if path.exists():
                raspistill = path
                break
        else:
            return None

        # Fix changed AWB values
        valid_awb = ["auto", "incandescent", "tungsten", "fluorescent", "indoor", "daylight", "cloudy"]
        if self.awb == "sunlight":
            self.awb = "daylight"
        self.awb = "auto" if self.awb not in valid_awb else self.awb

        # libcamera-still and rpicam-still require --immediate/--nopreview to avoid hanging
        extra = []
        if "libcamera-still" in str(raspistill) or "rpicam-still" in str(raspistill):
            extra = ["--immediate", "--nopreview"]

        return [str(raspistill), "--quality", "95", "--timeout", str(self._WARM_UP * 1000), "--encoding", "jpg", *extra]

    def _get_raw_data(self):
        if self._device["device"] is None:
            return False

        cmd = self._device["device"] + [
            "--width",
            str(self.width),
            "--height",
            str(self.height),
            "--awb",
            self.awb,
            "--output",
            "-",
        ]
        logger.debug(f"Starting rpicam: {cmd}")

        with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False) as proc:
            out, _ = proc.communicate()
            return BytesIO(out)

        return False
