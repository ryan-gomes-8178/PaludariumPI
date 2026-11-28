# -*- coding: utf-8 -*-
"""Nature Documentary Mode orchestration for TerrariumPI."""

import json
import os
import queue
import shlex
import shutil
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from pony import orm

import terrariumLogging

from terrariumDatabase import NatureDocClip, NatureDocEvent, Enclosure, Webcam
from terrariumUtils import terrariumUtils

logger = terrariumLogging.logging.getLogger(__name__)


@dataclass
class CameraConfig:
    camera_id: str
    stream_url: str
    enclosure_id: Optional[str] = None


@dataclass
class ClipJob:
    camera_id: str
    start_time: datetime
    end_time: datetime
    confidence: float
    event_ids: List[str]
    payloads: List[Dict]
    processing: bool = False

    def extend(self, new_end: datetime, confidence: float, event_id: str, payload: Dict):
        if new_end > self.end_time:
            self.end_time = new_end
        self.confidence = max(self.confidence, confidence)
        self.event_ids.append(event_id)
        self.payloads.append(payload)

    @property
    def duration(self) -> float:
        return max(1.0, (self.end_time - self.start_time).total_seconds())


class SegmentRecorder(threading.Thread):
    """Maintains rolling ffmpeg recording for a single camera."""

    def __init__(self, camera_id: str, stream_url: str, segment_seconds: int, output_dir: Path):
        super().__init__(daemon=True)
        self.camera_id = camera_id
        self.stream_url = stream_url
        self.segment_seconds = max(2, segment_seconds)
        self.output_dir = output_dir
        self._stop_event = threading.Event()
        self.process: Optional[subprocess.Popen] = None

    def stop(self):
        self._stop_event.set()
        if self.process and self.process.poll() is None:
            try:
                self.process.send_signal(signal.SIGTERM)
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()

    def run(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        while not self._stop_event.is_set():
            command = [
                "ffmpeg",
                "-nostdin",
                "-loglevel",
                "error",
                "-rtsp_transport",
                "tcp",
                "-i",
                self.stream_url,
                "-c",
                "copy",
                "-f",
                "segment",
                "-segment_time",
                str(self.segment_seconds),
                "-reset_timestamps",
                "1",
                "-strftime",
                "1",
                str(self.output_dir / "%Y%m%d_%H%M%S.ts"),
            ]

            try:
                logger.info("Starting ffmpeg segmenter for %s", self.camera_id)
                self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.process.wait()
                if self._stop_event.is_set():
                    break
                logger.warning("Segmenter for %s exited unexpectedly. Restarting in 5s", self.camera_id)
                time.sleep(5)
            except FileNotFoundError:
                logger.error("ffmpeg not installed. Nature Documentary recording disabled for %s", self.camera_id)
                break
            except Exception as exc:
                logger.error("Segment recorder error for %s: %s", self.camera_id, exc)
                time.sleep(2)


class NatureDocService:
    """Coordinates highlight creation pipeline."""

    def __init__(self, engine):
        self.engine = engine
        self.running = False
        self.job_queue: "queue.Queue[Optional[ClipJob]]" = queue.Queue()
        self.worker = threading.Thread(target=self._worker_loop, daemon=True)
        self.retention_thread = threading.Thread(target=self._retention_loop, daemon=True)
        self.recorders: Dict[str, SegmentRecorder] = {}
        self.camera_states: Dict[str, Dict] = {}

        self.config = self._load_config(engine.settings.get("nature_doc_config", "{}"))
        self.storage_root = Path(self.config.get("storage_path", "media/nature_doc"))
        self.segment_root = self.storage_root / "segments"
        self.clip_root = self.storage_root / "clips"
        self.preview_root = self.storage_root / "previews"
        for path in (self.segment_root, self.clip_root, self.preview_root):
            path.mkdir(parents=True, exist_ok=True)

        self.pre_roll = timedelta(seconds=int(self.config.get("pre_roll_seconds", 8)))
        self.post_roll = timedelta(seconds=int(self.config.get("post_roll_seconds", 15)))
        self.merge_window = timedelta(seconds=int(self.config.get("merge_window_seconds", 20)))
        self.cooldown = timedelta(seconds=int(self.config.get("cooldown_seconds", 60)))
        self.min_confidence = float(self.config.get("min_confidence", 0.3))
        self.segment_seconds = int(self.config.get("segment_seconds", 5))
        self.retention_hours = int(self.config.get("segment_retention_hours", 12))
        self.clip_retention_days = int(self.config.get("clip_retention_days", 30))
        self.ingest_token = self.config.get("ingest_token") or None

        self.camera_configs: Dict[str, CameraConfig] = self._resolve_cameras(self.config.get("cameras", {}))

    def _load_config(self, raw_value: str) -> Dict:
        if isinstance(raw_value, dict):
            return raw_value
        try:
            return json.loads(raw_value)
        except Exception:
            logger.warning("Invalid nature_doc_config JSON. Using defaults.")
            return {}

    def _resolve_cameras(self, camera_cfg: Dict) -> Dict[str, CameraConfig]:
        configs: Dict[str, CameraConfig] = {}
        if not camera_cfg:
            # Try to auto-map webcams by ID
            with orm.db_session:
                for webcam in Webcam.select():
                    stream = f"http://{self.engine.settings['host']}:{self.engine.settings['port']}/webcam/{webcam.id}/stream.m3u8"
                    configs[webcam.id] = CameraConfig(webcam.id, stream, webcam.enclosure.id if webcam.enclosure else None)
            return configs

        for camera_id, cfg in camera_cfg.items():
            stream = cfg.get("stream_url")
            enclosure_id = cfg.get("enclosure_id")
            if not stream:
                with orm.db_session:
                    webcam = Webcam.get(id=camera_id)
                    if webcam:
                        stream = f"http://{self.engine.settings['host']}:{self.engine.settings['port']}/webcam/{webcam.id}/stream.m3u8"
                        enclosure_id = enclosure_id or (webcam.enclosure.id if webcam.enclosure else None)
            if not stream:
                logger.warning("Camera %s missing stream_url", camera_id)
                continue
            configs[camera_id] = CameraConfig(camera_id, stream, enclosure_id)
        return configs

    def authorize(self, provided_token: Optional[str]) -> bool:
        if not self.ingest_token:
            return True
        return terrariumUtils.safe_str_cmp(self.ingest_token, provided_token or "")

    def start(self):
        if not self.config.get("enabled", False):
            logger.info("Nature Documentary Mode disabled")
            return
        self.running = True
        self._start_recorders()
        self.worker.start()
        self.retention_thread.start()
        logger.info("Nature Documentary Mode online for %d camera(s)", len(self.camera_configs))

    def stop(self):
        if not self.running:
            return
        self.running = False
        self.job_queue.put(None)
        for recorder in self.recorders.values():
            recorder.stop()
        self.worker.join(timeout=5)
        self.retention_thread.join(timeout=5)

    def _start_recorders(self):
        for camera_id, cfg in self.camera_configs.items():
            segment_dir = self.segment_root / camera_id
            recorder = SegmentRecorder(camera_id, cfg.stream_url, self.segment_seconds, segment_dir)
            recorder.start()
            self.recorders[camera_id] = recorder
            self.camera_states[camera_id] = {
                "lock": threading.Lock(),
                "pending": None,
                "last_clip_end": None,
            }

    def enqueue_events(self, camera_id: str, events: List[Dict]) -> Dict:
        if not self.running:
            return {"accepted": 0, "detail": "service-disabled"}
        if camera_id not in self.camera_configs:
            logger.warning("Unknown camera_id %s in NatureDoc ingest", camera_id)
            return {"accepted": 0, "detail": "unknown-camera"}

        accepted = []
        for payload in events:
            event_id = self._record_event(camera_id, payload)
            if not event_id:
                continue
            accepted.append(event_id)
        return {"accepted": len(accepted), "event_ids": accepted}

    def _record_event(self, camera_id: str, payload: Dict) -> Optional[str]:
        timestamp = self._parse_timestamp(payload.get("timestamp"))
        confidence = float(payload.get("confidence", 0))
        if confidence < self.min_confidence:
            return None

        bbox = payload.get("bounding_box", {})
        track_id = payload.get("track_id")
        zone = payload.get("zone")

        with orm.db_session:
            enclosure = None
            cfg = self.camera_configs.get(camera_id)
            if cfg and cfg.enclosure_id:
                enclosure = Enclosure.get(id=cfg.enclosure_id)
            event = NatureDocEvent(
                camera_id=camera_id,
                enclosure=enclosure,
                timestamp=timestamp,
                confidence=confidence,
                track_id=str(track_id) if track_id is not None else None,
                bbox=bbox,
                meta={"zone": zone, "centroid": payload.get("centroid")},
            )
        event_id = event.id
        self._maybe_schedule_job(camera_id, event_id, timestamp, confidence, payload)
        return event_id

    def _maybe_schedule_job(self, camera_id: str, event_id: str, timestamp: datetime, confidence: float, payload: Dict):
        state = self.camera_states[camera_id]
        with state["lock"]:
            last_end = state["last_clip_end"]
            if last_end and timestamp <= (last_end + self.cooldown):
                with orm.db_session:
                    NatureDocEvent[event_id].status = "cooldown"
                return

            pending: Optional[ClipJob] = state["pending"]
            if pending and not pending.processing and timestamp <= (pending.end_time + self.merge_window):
                pending.extend(timestamp + self.post_roll, confidence, event_id, payload)
                with orm.db_session:
                    NatureDocEvent[event_id].status = "merged"
                return

            job = ClipJob(
                camera_id=camera_id,
                start_time=timestamp - self.pre_roll,
                end_time=timestamp + self.post_roll,
                confidence=confidence,
                event_ids=[event_id],
                payloads=[payload],
            )
            state["pending"] = job
            self.job_queue.put(job)
            with orm.db_session:
                NatureDocEvent[event_id].status = "queued"

    def _worker_loop(self):
        while True:
            job = self.job_queue.get()
            if job is None:
                break
            state = self.camera_states.get(job.camera_id)
            if state:
                with state["lock"]:
                    job.processing = True
                    state["pending"] = None
            try:
                self._process_job(job)
            except Exception as exc:
                logger.error("Clip job failed for %s: %s", job.camera_id, exc)
            finally:
                self.job_queue.task_done()

    def _process_job(self, job: ClipJob):
        segments = self._collect_segments(job.camera_id, job.start_time, job.end_time)
        if not segments:
            logger.warning("No segments found for %s between %s and %s", job.camera_id, job.start_time, job.end_time)
            with orm.db_session:
                for event_id in job.event_ids:
                    NatureDocEvent[event_id].status = "missing-video"
            return

        clip_path = self._render_clip(job, segments)
        preview_path = self._render_preview(clip_path)

        metadata = {
            "events": job.payloads,
            "segments": [seg.as_posix() for seg in segments],
        }

        with orm.db_session:
            enclosure = None
            cfg = self.camera_configs.get(job.camera_id)
            if cfg and cfg.enclosure_id:
                enclosure = Enclosure.get(id=cfg.enclosure_id)
            event = NatureDocEvent[job.event_ids[0]]
            clip = NatureDocClip(
                event=event,
                enclosure=enclosure,
                camera_id=job.camera_id,
                start_time=job.start_time,
                end_time=job.end_time,
                duration=job.duration,
                confidence=job.confidence,
                filepath=str(clip_path),
                preview_path=str(preview_path) if preview_path else None,
                metadata=metadata,
                score=round(job.duration * job.confidence, 2),
            )
            NatureDocEvent[event.id].status = "completed"
            for extra in job.event_ids[1:]:
                NatureDocEvent[extra].status = "attached"

        state = self.camera_states[job.camera_id]
        with state["lock"]:
            state["last_clip_end"] = job.end_time

    def _render_clip(self, job: ClipJob, segments: List[Path]) -> Path:
        concat_file = self.storage_root / f"tmp_concat_{job.camera_id}.txt"
        with concat_file.open("w") as fh:
            for seg in segments:
                fh.write(f"file '{seg.as_posix()}'\n")

        temp_output = self.storage_root / f"tmp_{job.camera_id}_{int(time.time())}.mp4"
        # First concat raw segments
        command_concat = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(temp_output),
        ]
        self._run_ffmpeg(command_concat)

        clip_dir = self.clip_root / job.camera_id
        clip_dir.mkdir(parents=True, exist_ok=True)
        clip_path = clip_dir / f"{job.start_time.strftime('%Y%m%d_%H%M%S')}_{job.event_ids[0]}.mp4"

        start_offset = max(0.0, (job.start_time - self._segment_timestamp(segments[0])).total_seconds())
        trim_command = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-ss",
            f"{start_offset:.3f}",
            "-i",
            str(temp_output),
            "-t",
            f"{job.duration:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "21",
            "-c:a",
            "aac",
            str(clip_path),
        ]
        self._run_ffmpeg(trim_command)

        concat_file.unlink(missing_ok=True)
        temp_output.unlink(missing_ok=True)
        return clip_path

    def _render_preview(self, clip_path: Path) -> Optional[Path]:
        preview_dir = self.preview_root / clip_path.parent.name
        preview_dir.mkdir(parents=True, exist_ok=True)
        preview_path = preview_dir / (clip_path.stem + ".gif")
        command = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(clip_path),
            "-vf",
            "fps=10,scale=480:-1:flags=lanczos",
            "-loop",
            "0",
            str(preview_path),
        ]
        try:
            self._run_ffmpeg(command)
            return preview_path
        except Exception as exc:
            logger.warning("Preview generation failed for %s: %s", clip_path, exc)
            return None

    def _collect_segments(self, camera_id: str, start: datetime, end: datetime) -> List[Path]:
        segment_dir = self.segment_root / camera_id
        if not segment_dir.exists():
            return []
        segments = []
        for file in sorted(segment_dir.glob("*.ts")):
            seg_start = self._segment_timestamp(file)
            seg_end = seg_start + timedelta(seconds=self.segment_seconds)
            if seg_end < start:
                continue
            if seg_start > end:
                break
            segments.append(file)
        return segments

    def _segment_timestamp(self, file_path: Path) -> datetime:
        try:
            ts_str = file_path.stem
            return datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
        except ValueError:
            return datetime.fromtimestamp(file_path.stat().st_mtime)

    def _run_ffmpeg(self, command: List[str]):
        logger.debug("Running ffmpeg: %s", shlex.join(command))
        result = subprocess.run(command, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode())

    def _retention_loop(self):
        while self.running:
            self._cleanup_segments()
            self._cleanup_clips()
            time.sleep(3600)

    def _cleanup_segments(self):
        cutoff = datetime.now() - timedelta(hours=self.retention_hours)
        for camera_id in self.camera_configs:
            segment_dir = self.segment_root / camera_id
            if not segment_dir.exists():
                continue
            for file in segment_dir.glob("*.ts"):
                seg_time = self._segment_timestamp(file)
                if seg_time < cutoff:
                    file.unlink(missing_ok=True)

    def _cleanup_clips(self):
        cutoff = datetime.now() - timedelta(days=self.clip_retention_days)
        for clip_file in self.clip_root.rglob("*.mp4"):
            if datetime.fromtimestamp(clip_file.stat().st_mtime) < cutoff:
                preview = self.preview_root / clip_file.relative_to(self.clip_root)
                preview = preview.with_suffix(".gif")
                clip_file.unlink(missing_ok=True)
                preview.unlink(missing_ok=True)

    def list_clips(self, limit: int = 50, offset: int = 0) -> Dict:
        with orm.db_session:
            total = NatureDocClip.select().count()
            clips = NatureDocClip.select().order_by(orm.desc(NatureDocClip.created))[offset : offset + limit]
            return {
                "total": total,
                "clips": [self._clip_to_dict(c) for c in clips],
            }

    def get_clip(self, clip_id: str) -> Optional[NatureDocClip]:
        with orm.db_session:
            return NatureDocClip.get(id=clip_id)

    def mark_favorite(self, clip_id: str, favorite: bool) -> bool:
        with orm.db_session:
            clip = NatureDocClip.get(id=clip_id)
            if not clip:
                return False
            clip.favorite = favorite
            return True

    def _clip_to_dict(self, clip: NatureDocClip) -> Dict:
        return {
            "id": clip.id,
            "camera_id": clip.camera_id,
            "start_time": clip.start_time.isoformat(),
            "end_time": clip.end_time.isoformat(),
            "duration": clip.duration,
            "confidence": clip.confidence,
            "score": clip.score,
            "favorite": clip.favorite,
            "status": clip.status,
            "media_url": f"/api/nature-doc/clips/{clip.id}/media",
            "preview_url": f"/api/nature-doc/clips/{clip.id}/preview" if clip.preview_path else None,
            "metadata": clip.metadata,
        }

    def _cleanup_orphan_clip_files(self):
        with orm.db_session:
            known_files = {Path(c.filepath) for c in NatureDocClip.select()}
        for clip_file in self.clip_root.rglob("*.mp4"):
            if clip_file not in known_files:
                clip_file.unlink(missing_ok=True)

    def _parse_timestamp(self, value: Optional[str]) -> datetime:
        if not value:
            return datetime.utcnow()
        try:
            if value.endswith("Z"):
                value = value.replace("Z", "+00:00")
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime.utcnow()
