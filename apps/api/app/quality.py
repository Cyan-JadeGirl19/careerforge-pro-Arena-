"""Transparent, file-based video quality checks.

These checks measure the actual file (length, resolution, frame rate,
audio presence/level, pauses, lighting) and report pass/warn/fail with
a plain-language tip. No invented scores, no "ATS %"-style theatre -
the candidate sees exactly what was measured.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .ffmpegx import MediaProbe


def build_report(
    probe: MediaProbe,
    audio: dict,
    silences: list[tuple[float, float]],
    lighting: float | None,
    target_seconds: int | None = None,
) -> dict:
    checks: list[dict] = []

    def add(check_id: str, label: str, status: str, detail: str, tip: str | None = None):
        checks.append(
            {"id": check_id, "label": label, "status": status,
             "detail": detail, "tip": tip}
        )

    # --- length ---------------------------------------------------------
    d = probe.duration
    if not d:
        add("duration", "Length", "fail", "could not read the video length",
            "Re-export the file as MP4 from your camera or phone app.")
    elif d > 185:
        add("duration", "Length", "warn", f"{d:.0f}s",
            "Many employers cap videos at 3 minutes - consider a tighter cut "
            "or trim the quietest part.")
    elif d < 10:
        add("duration", "Length", "warn", f"{d:.0f}s",
            "That is very short for a video application - most ask for 30s or more.")
    elif target_seconds and d > target_seconds * 1.4:
        add("duration", "Length", "warn", f"{d:.0f}s vs your {target_seconds}s target",
            "A little over is fine, but much longer risks losing the reader.")
    else:
        add("duration", "Length", "pass", f"{d:.1f}s", None)

    # --- resolution -----------------------------------------------------
    if probe.width and probe.height:
        m = min(probe.width, probe.height)
        res = f"{probe.width}x{probe.height}"
        if m < 360:
            add("resolution", "Resolution", "fail", res,
                "That is too low - most employers expect at least 480p.")
        elif m < 480:
            add("resolution", "Resolution", "warn", res,
                "Usable, but 720p looks noticeably more professional.")
        else:
            add("resolution", "Resolution", "pass", res, None)
    else:
        add("resolution", "Resolution", "fail", "no video stream found",
            "Re-export the file as MP4 from your camera or phone app.")

    # --- frame rate -----------------------------------------------------
    if probe.fps:
        if probe.fps < 18:
            add("frame_rate", "Frame rate", "warn", f"{probe.fps:.0f} fps",
                "Low frame rates look stuttery - re-record if you can.")
        else:
            add("frame_rate", "Frame rate", "pass", f"{probe.fps:.0f} fps", None)
    else:
        add("frame_rate", "Frame rate", "pass", "not reported", None)

    # --- audio ----------------------------------------------------------
    if not probe.audio_codec:
        add("audio_present", "Audio", "fail", "no audio track",
            "A video answer without audio is a broken file - re-record.")
    else:
        add("audio_present", "Audio", "pass", probe.audio_codec, None)
        mean = audio.get("mean_volume")
        mx = audio.get("max_volume")
        if mean is not None and mean < -35:
            add("audio_level", "Volume", "warn",
                f"mean {mean:.0f} dB", "Sounds quiet - use 'Normalize audio' in "
                "Enhance, or re-record closer to the mic.")
        elif mx is not None and mx < -22:
            add("audio_level", "Volume", "warn", f"peak {mx:.0f} dB",
                "Low level - normalize or re-record.")
        else:
            detail = f"mean {mean:.0f} dB" if mean is not None else "measured"
            add("audio_level", "Volume", "pass", detail, None)

    # --- pauses ---------------------------------------------------------
    total = sum(x[1] for x in silences)
    longest = max((x[1] for x in silences), default=0.0)
    if probe.audio_codec and probe.duration:
        if longest > 4 or total > 0.2 * probe.duration:
            add("pauses", "Pauses", "warn",
                f"{len(silences)} pause(s), longest {longest:.1f}s",
                "Dead air reads as unprepared - tighten it, or accept the pauses "
                "if they sit at natural sentence breaks.")
        else:
            add("pauses", "Pauses", "pass",
                f"{len(silences)} pause(s), longest {longest:.1f}s", None)

    # --- lighting -------------------------------------------------------
    if lighting is None:
        add("lighting", "Lighting", "pass", "could not measure",
            "If you are unsure, face a window - light on your face, not behind you.")
    elif lighting < 45:
        add("lighting", "Lighting", "warn", f"average brightness {lighting:.0f}/255",
            "Looks dark - face a light source and re-record if you can.")
    elif lighting > 215:
        add("lighting", "Lighting", "warn", f"average brightness {lighting:.0f}/255",
            "Looks overexposed - step back from the light.")
    else:
        add("lighting", "Lighting", "pass", f"average brightness {lighting:.0f}/255", None)

    by_status = {"pass": 0, "warn": 0, "fail": 0}
    for c in checks:
        by_status[c["status"]] = by_status.get(c["status"], 0) + 1
    return {
        "summary": {
            "ready": by_status["fail"] == 0,
            "pass": by_status["pass"],
            "warn": by_status["warn"],
            "fail": by_status["fail"],
        },
        "checks": checks,
        "probe": probe.to_dict(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": ("These checks measure the file itself - length, resolution, "
                 "audio level, pauses and brightness. Nothing is hidden, "
                 "scored mysteriously, or adjusted."),
    }
