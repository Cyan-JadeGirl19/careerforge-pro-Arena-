"""FFmpeg helpers on top of the bundled static binary (imageio-ffmpeg).

Design notes
------------
- Media lives in the database (see VideoMedia), so everything here
  operates on raw bytes and uses temp files only for the duration of a
  single operation. Ephemeral deploy filesystems (Render free tier)
  never matter.
- The static build ships with libx264, libmp3lame, aac and the
  filters we need (eq, loudnorm, silencedetect, signalstats,
  subtitles), so no system ffmpeg installation is required anywhere:
  sandbox, CI or Render.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator

from imageio_ffmpeg import get_ffmpeg_exe
from PIL import Image, ImageDraw, ImageFont

FFMPEG_BIN = get_ffmpeg_exe()

MAX_UPLOAD_BYTES = 150 * 1024 * 1024  # 150 MB hard cap
ALLOWED_CONTENT_TYPES = {
    "video/webm",
    "video/mp4",
    "video/quicktime",
    "video/x-m4v",
    "video/mpeg",
}
VIDEO_KINDS = {"original", "enhanced"}


def ffmpeg_bin() -> str:
    return FFMPEG_BIN


def run_ffmpeg(
    args: list[str], *, timeout: int = 900, ok_codes: tuple[int, ...] = (0,)
) -> subprocess.CompletedProcess:
    """Run ffmpeg; raise RuntimeError with a stderr tail on failure."""
    try:
        proc = subprocess.run(
            [FFMPEG_BIN, *args], capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ffmpeg timed out after {timeout}s") from exc
    if proc.returncode not in ok_codes:
        tail = (proc.stderr or proc.stdout or "").strip()[-1500:]
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}): {tail}")
    return proc


@contextmanager
def temp_media(data: bytes, suffix: str = ".mp4") -> Iterator[Path]:
    """Write bytes to a temp file; always removes it afterwards."""
    fd, path = tempfile.mkstemp(suffix=suffix, prefix="cfmedia-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        yield Path(path)
    finally:
        _unlink(path)


@contextmanager
def temp_out(suffix: str = ".mp4") -> Iterator[Path]:
    """An empty temp file ffmpeg can encode into; removed afterwards."""
    fd, path = tempfile.mkstemp(suffix=suffix, prefix="cfout-")
    os.close(fd)
    try:
        yield Path(path)
    finally:
        _unlink(path)


def _unlink(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


# --- probing -----------------------------------------------------------------


@dataclass
class MediaProbe:
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    sample_rate: int | None = None
    video_bitrate: int | None = None  # bits/s
    audio_bitrate: int | None = None  # bits/s
    size: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def _bitrate(text: str) -> int | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(kb/s|Mbps|bit/s)", text)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2)
    if unit == "kb/s":
        return int(val * 1000)
    if unit == "Mbps":
        return int(val * 1_000_000)
    return int(val)


def probe_path(path: Path) -> MediaProbe:
    """Probe a file by parsing `ffmpeg -i` (no ffprobe needed)."""
    proc = run_ffmpeg(
        ["-hide_banner", "-i", str(path)], ok_codes=(0, 1), timeout=120
    )
    out = proc.stderr or ""
    p = MediaProbe(size=path.stat().st_size)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", out)
    if m:
        p.duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    for line in out.splitlines():
        if "Video:" in line and p.video_codec is None:
            p.video_codec = line.split("Video:", 1)[1].split(",", 1)[0].strip()
            wm = re.search(r"(\d{2,5})x(\d{2,5})", line)
            if wm:
                p.width, p.height = int(wm.group(1)), int(wm.group(2))
            fm = re.search(r"(\d+(?:\.\d+)?)\s*fps", line)
            if fm:
                p.fps = float(fm.group(1))
            p.video_bitrate = _bitrate(line)
        elif "Audio:" in line and p.audio_codec is None:
            p.audio_codec = line.split("Audio:", 1)[1].split(",", 1)[0].strip()
            sm = re.search(r"(\d+)\s*Hz", line)
            if sm:
                p.sample_rate = int(sm.group(1))
            p.audio_bitrate = _bitrate(line)
    return p


def probe_media(data: bytes, suffix: str = ".mp4") -> MediaProbe:
    with temp_media(data, suffix=suffix) as path:
        return probe_path(path)


# --- analysis (quality checks) -------------------------------------------------


def analyze_audio(path: Path) -> dict:
    """Mean/max loudness via volumedetect."""
    proc = run_ffmpeg(
        ["-hide_banner", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
        timeout=600,
    )
    out = proc.stderr or ""
    mean = re.search(r"mean_volume:\s*(-?[\d.]+)\s*dB", out)
    mx = re.search(r"max_volume:\s*(-?[\d.]+)\s*dB", out)
    return {
        "mean_volume": float(mean.group(1)) if mean else None,
        "max_volume": float(mx.group(1)) if mx else None,
    }


def detect_silences(
    path: Path, noise_db: float = -30.0, min_duration: float = 0.8
) -> list[tuple[float, float]]:
    """Return (start, duration) pairs of silences of at least min_duration."""
    proc = run_ffmpeg(
        [
            "-hide_banner",
            "-i",
            str(path),
            "-af",
            f"silencedetect=noise={noise_db}dB:d={min_duration}",
            "-f",
            "null",
            "-",
        ],
        timeout=600,
    )
    out = proc.stderr or ""
    starts = [float(x) for x in re.findall(r"silence_start:\s*(-?[\d.]+)", out)]
    durs = [float(x) for x in re.findall(r"silence_duration:\s*(-?[\d.]+)", out)]
    return list(zip(starts, durs))


def measure_lighting(path: Path, frames: int = 300) -> float | None:
    """Average Y (luma) over the first `frames` frames - a lighting signal.

    ~0-255 scale: < 45 tends to look dark, > 215 tends to look
    overexposed on a typical camera.
    """
    proc = run_ffmpeg(
        [
            "-hide_banner",
            "-i",
            str(path),
            "-vf",
            f"trim=end_frame={frames},signalstats,metadata=print",
            "-f",
            "null",
            "-",
        ],
        timeout=600,
    )
    out = proc.stderr or ""
    vals = [float(x) for x in re.findall(r"lavfi\.signalstats\.YAVG=([\d.]+)", out)]
    if not vals:
        return None
    return sum(vals) / len(vals)


# --- enhancement filters --------------------------------------------------------


def build_video_filters(
    *,
    brightness: int = 0,
    contrast: int = 0,
    saturation: int = 0,
    framing: str = "none",
) -> str | None:
    """Map UI slider values (-10..10) onto the eq filter + framing crops."""
    parts: list[str] = []
    if brightness or contrast or saturation:
        parts.append(
            f"eq=brightness={brightness * 0.02:.3f}:"
            f"contrast={1 + contrast * 0.02:.3f}:"
            f"saturation={1 + saturation * 0.03:.3f}"
        )
    if framing == "16x9":
        # keep the full frame, letterbox into a clean 720p
        parts.append("scale=1280:720:force_original_aspect_ratio=decrease")
        parts.append("pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black")
        parts.append("setsar=1")
    elif framing == "9x16":
        # center-crop to vertical, then scale (even dims for h264).
        # Expressions are single-quoted: the filtergraph parser splits
        # unquoted values on ':' (option separator).
        parts.append(
            "crop='2*trunc(min(iw,ih*9/16)/2)':'2*trunc(min(ih,iw*16/9)/2)'"
        )
        parts.append("scale=720:1280")
        parts.append("setsar=1")
    elif framing == "1x1":
        parts.append("crop='2*trunc(min(iw,ih)/2)':'2*trunc(min(ih,iw)/2)'")
        parts.append("scale=720:720")
        parts.append("setsar=1")
    return ",".join(parts) if parts else None


def build_audio_filters(normalize: bool) -> str | None:
    if not normalize:
        return None
    # Speech-friendly target level (slightly hotter than music).
    return "loudnorm=I=-16:TP=-1.5:LRA=11"


def _subtitles_filter(path: Path) -> str:
    p = str(path).replace("\\", "\\\\").replace(":", r"\:").replace("'", "\\'")
    return (
        "subtitles=filename='" + p + "':force_style="
        "'FontName=DejaVu Sans,FontSize=16,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,Outline=1,Shadow=0,MarginV=24'"
    )


def reencode_mp4(
    src: Path,
    dst: Path,
    *,
    vfilter: str | None = None,
    afilter: str | None = None,
    burn_vtt: Path | None = None,
    has_audio: bool = True,
    timeout: int = 1500,
) -> None:
    """Encode to H.264/AAC MP4 (faststart, 720p-class).

    `veryfast` keeps CPU/memory low (Render free tier) while staying
    well within quality for application videos.
    """
    vf: list[str] = []
    if vfilter:
        vf.append(vfilter)
    if burn_vtt is not None:
        vf.append(_subtitles_filter(burn_vtt))
    args = ["-hide_banner", "-y", "-i", str(src)]
    if vf:
        args += ["-vf", ",".join(vf)]
    if afilter and has_audio:
        args += ["-af", afilter]
    args += [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
        "-pix_fmt", "yuv420p", "-profile:v", "high",
    ]
    if has_audio:
        args += ["-c:a", "aac", "-b:a", "160k"]
    else:
        args += ["-an"]
    args += ["-movflags", "+faststart", str(dst)]
    run_ffmpeg(args, timeout=timeout)


def extract_mp3(src: Path, dst: Path, timeout: int = 600) -> None:
    run_ffmpeg(
        ["-hide_banner", "-y", "-i", str(src), "-vn", "-c:a", "libmp3lame",
         "-q:a", "3", str(dst)],
        timeout=timeout,
    )


def make_test_clip(path: Path, seconds: int = 6) -> None:
    """Generate a small h264/aac test clip (tests only)."""
    run_ffmpeg(
        [
            "-hide_banner", "-y",
            "-f", "lavfi", "-i", f"testsrc2=size=640x360:rate=30:duration={seconds}",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path),
        ],
        timeout=300,
    )


# --- trimming, intro cards, thumbnails -----------------------------------------

# Fonts are committed to the repo (DejaVu - freely licensed) so drawtext
# works on hosts without system fonts (Render buildpack image included).
FONT_DIR = Path(__file__).resolve().parent / "fonts"
FONT_REGULAR = FONT_DIR / "DejaVuSans.ttf"
FONT_BOLD = FONT_DIR / "DejaVuSans-Bold.ttf"

INTRO_W, INTRO_H, INTRO_FPS = 1280, 720, 30


def _sanitize_text(value: str, max_len: int = 60) -> str:
    """Tidy a name/role for the intro card (unicode-safe, length-capped)."""
    out = re.sub(r"[\x00-\x1f\x7f]", " ", (value or "").strip())
    out = re.sub(r"\s+", " ", out)
    return out[:max_len].strip()


def build_intro_image(
    dst: Path, headshot: Path, name: str, role: str
) -> None:
    """Render the intro card as a 1280x720 PNG (Pillow - no ffmpeg text
    filters required, so it works on hosts without system fonts)."""
    bg = Image.new("RGB", (INTRO_W, INTRO_H), (16, 18, 22))
    # headshot in a fixed 500x460 box, top-right
    try:
        photo = Image.open(headshot).convert("RGB")
    except Exception:
        photo = None
    if photo is not None:
        photo.thumbnail((500, 460), Image.LANCZOS)
        box = Image.new("RGB", (500, 460), (16, 18, 22))
        box.paste(photo, ((500 - photo.width) // 2, (460 - photo.height) // 2))
        bg.paste(box, (720, 130))
    draw = ImageDraw.Draw(bg)
    name = _sanitize_text(name, 40) or "Candidate"
    role = _sanitize_text(role, 80)

    def fit(size: int, max_px: int) -> int:
        f = ImageFont.truetype(str(FONT_BOLD), size)
        while size > 36 and draw.textlength(name, font=f) > max_px:
            size -= 4
            f = ImageFont.truetype(str(FONT_BOLD), size)
        return size

    name_size = fit(84, 1120)
    draw.text((80, 270), name, font=ImageFont.truetype(str(FONT_BOLD), name_size), fill=(255, 255, 255))
    if role:
        role_size = 44
        rf = ImageFont.truetype(str(FONT_REGULAR), role_size)
        while role_size > 24 and draw.textlength(role, font=rf) > 1120:
            role_size -= 2
            rf = ImageFont.truetype(str(FONT_REGULAR), role_size)
        draw.text((80, 410), role, font=rf, fill=(170, 178, 191))
    bg.save(dst)


def trim_video(src: Path, dst: Path, start: float, end: float, timeout: int = 900) -> None:
    """Cut [start, end] out of the source and re-encode to MP4."""
    run_ffmpeg(
        [
            "-hide_banner", "-y",
            "-ss", f"{max(0.0, start):.3f}",
            "-t", f"{max(0.0, end - start):.3f}",
            "-i", str(src),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart", str(dst),
        ],
        timeout=timeout,
    )


def build_intro_card(dst: Path, card: Path, seconds: int, timeout: int = 600) -> None:
    """Turn the rendered card PNG into a silent H.264 intro clip."""
    run_ffmpeg(
        [
            "-hide_banner", "-y",
            "-loop", "1", "-framerate", str(INTRO_FPS), "-i", str(card),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", str(seconds),
            "-vf", f"scale={INTRO_W}:{INTRO_H},format=yuv420p",
            "-r", str(INTRO_FPS),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
            "-shortest", str(dst),
        ],
        timeout=timeout,
    )


def normalize_source(src: Path, dst: Path, has_audio: bool, timeout: int = 900) -> None:
    """Re-encode to exactly the concat-target params (1280x720@30, aac 44.1k)."""
    args = ["-hide_banner", "-y"]
    if not has_audio:
        # silent audio is input 0, the source is input 1
        args += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
        video_map, audio_map = "1:v:0", "0:a:0"
    else:
        video_map, audio_map = "0:v:0", "0:a:0"
    args += [
        "-i", str(src),
        "-map", video_map,
        "-map", audio_map,
        "-vf",
        f"scale={INTRO_W}:{INTRO_H}:force_original_aspect_ratio=decrease,"
        f"pad={INTRO_W}:{INTRO_H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1",
        "-r", str(INTRO_FPS),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
    ]
    if not has_audio:
        args += ["-shortest"]
    args += ["-movflags", "+faststart", str(dst)]
    run_ffmpeg(args, timeout=timeout)


def concat_mp4(parts: list[Path], dst: Path, timeout: int = 300) -> None:
    """Stream-copy concat (all parts must share codec parameters)."""
    fd, list_path = tempfile.mkstemp(suffix=".txt", prefix="cfconcat-")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write("".join(f"file '{p}'\n" for p in parts))
        run_ffmpeg(
            ["-hide_banner", "-y", "-f", "concat", "-safe", "0",
             "-i", list_path, "-c", "copy", str(dst)],
            timeout=timeout,
        )
    finally:
        _unlink(list_path)


def make_thumbnail(src: Path, dst: Path, at: float, timeout: int = 120) -> None:
    """A single 1280x720 PNG frame from the source."""
    run_ffmpeg(
        [
            "-hide_banner", "-y",
            "-ss", f"{max(0.0, at):.3f}", "-i", str(src),
            "-vf",
            f"scale={INTRO_W}:{INTRO_H}:force_original_aspect_ratio=decrease,"
            f"pad={INTRO_W}:{INTRO_H}:(ow-iw)/2:(oh-ih)/2:color=black",
            "-frames:v", "1", str(dst),
        ],
        timeout=timeout,
    )
