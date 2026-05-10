"""Video parser — extract audio with ffmpeg, then route through the audio
parser.

We do NOT do frame extraction or visual OCR. Out of scope. The agent treats
a recorded lecture as audio with timestamp metadata; the visual track is
ignored.

ffmpeg must be on PATH. On Replit / Linux this is typical; on Windows the
team needs `winget install Gyan.FFmpeg` or equivalent.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from agent.parsers.audio_parser import parse as parse_audio_internal
from agent.models import Document, SourceType

logger = logging.getLogger(__name__)


def parse(path: str | Path) -> Document:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg is not on PATH. Install it (e.g. `winget install Gyan.FFmpeg`)."
        )

    p = Path(path)
    with tempfile.TemporaryDirectory(prefix="agent_video_") as tmp:
        wav_path = Path(tmp) / "audio.wav"
        _extract_audio(p, wav_path)
        doc = parse_audio_internal(wav_path)

    # The audio parser stamped the `wav_path` and `SourceType.AUDIO`. Override
    # both to point back at the original video so downstream traceability and
    # serialization reflect the user-facing source.
    return Document(
        source_path=str(p),
        source_type=SourceType.VIDEO,
        blocks=doc.blocks,
        size_metric=doc.size_metric,
        parser_meta={**doc.parser_meta, "demuxer": "ffmpeg"},
    )


def _extract_audio(video: Path, out_wav: Path) -> None:
    cmd = [
        "ffmpeg",
        "-y",            # overwrite
        "-i", str(video),
        "-vn",           # no video
        "-ac", "1",      # mono
        "-ar", "16000",  # 16 kHz — Whisper's native rate
        "-loglevel", "error",
        str(out_wav),
    ]
    logger.info("Extracting audio: %s -> %s", video, out_wav)
    subprocess.run(cmd, check=True)
