"""Video Studio end-to-end: upload -> quality -> captions -> enhance -> exports.

A real 6s h264/aac test clip (test pattern + sine wave) is generated with
the bundled ffmpeg binary, so the whole pipeline runs for real -
including libx264 encoding, framing crops, loudness normalisation,
caption burn-in and MP3 extraction.
"""
import io
import os
import time

import pytest

from app import ffmpegx

API = "/api/v1"


@pytest.fixture(scope="module")
def test_clip(tmp_path_factory):
    d = tmp_path_factory.mktemp("clip")
    out = d / "clip.mp4"
    ffmpegx.make_test_clip(out, seconds=6)
    return out.read_bytes()


@pytest.fixture()
def media_profile(client, consented_profile) -> str:
    res = client.post(
        f"{API}/profiles/{consented_profile}/consents",
        json={"item": "media_use", "granted": True},
    )
    assert res.status_code == 201
    return consented_profile


@pytest.fixture()
def app_video(client, media_profile, cv_id) -> tuple[str, str, int]:
    """(application_id, video_id, target_seconds) with a real script."""
    jd = client.post(
        f"{API}/profiles/{media_profile}/job-descriptions",
        json={
            "title": "Support Specialist",
            "company": "Remote Co",
            "text": "We need a remote support specialist. Requirements: "
                    "SaaS support, remote work, written English.",
        },
    )
    assert jd.status_code == 201, jd.text
    app = client.post(
        f"{API}/profiles/{media_profile}/applications",
        json={"jd_id": jd.json()["id"]},
    )
    assert app.status_code == 201, app.text
    app_id = app.json()["id"]
    v = client.post(
        f"{API}/applications/{app_id}/videos",
        json={
            "question": "Tell us about yourself and why you fit this role.",
            "target_seconds": 60,
        },
    )
    assert v.status_code == 201, v.text
    return app_id, v.json()["id"], 60


def _upload(client, video_id: str, data: bytes, consent: bool = True):
    return client.post(
        f"{API}/videos/{video_id}/media-upload",
        files={"file": ("take.mp4", io.BytesIO(data), "video/mp4")},
        data={"likeness_consent": "true" if consent else "false"},
    )


def _wait_job(client, job_id: str, timeout_s: float = 240) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        res = client.get(f"{API}/jobs/video/{job_id}")
        assert res.status_code == 200
        st = res.json()
        if st["status"] != "running":
            return st
        time.sleep(0.5)
    raise AssertionError("job did not finish in time")


def test_upload_requires_likeness_consent(client, app_video, test_clip):
    _, video_id, _ = app_video
    res = _upload(client, video_id, test_clip, consent=False)
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "LIKENESS_CONSENT_REQUIRED"


def test_upload_rejects_bad_type(client, app_video):
    _, video_id, _ = app_video
    res = client.post(
        f"{API}/videos/{video_id}/media-upload",
        files={"file": ("notes.txt", io.BytesIO(b"hello" * 100), "text/plain")},
        data={"likeness_consent": "true"},
    )
    assert res.status_code == 415


def test_full_pipeline(client, app_video, test_clip):
    app_id, video_id, _ = app_video

    # 1. upload
    res = _upload(client, video_id, test_clip)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["media_status"] == "uploaded"
    assert body["likeness_consent"] is True
    assert len(body["media"]) == 1
    orig = body["media"][0]
    assert orig["kind"] == "original"
    assert orig["duration"] and 5 < orig["duration"] < 8
    mid = orig["id"]

    # 2. quality report
    res = client.post(f"{API}/videos/{video_id}/media/{mid}/analyze")
    assert res.status_code == 200, res.text
    report = res.json()["report"]
    ids = {c["id"] for c in report["checks"]}
    assert {
        "duration", "resolution", "frame_rate",
        "audio_present", "audio_level", "pauses", "lighting",
    } <= ids
    assert report["summary"]["fail"] == 0
    assert report["probe"]["width"] == 640

    # 3. captions from an explicit transcript
    res = client.post(
        f"{API}/videos/{video_id}/captions",
        json={
            "transcript": (
                "Hi, my name is Thando. I have six years in remote SaaS support. "
                "I am looking for my next role."
            )
        },
    )
    assert res.status_code == 201, res.text
    caps = [m for m in res.json()["media"] if m["kind"] == "captions"]
    assert len(caps) == 1
    cap_id = caps[0]["id"]
    dl = client.get(f"{API}/videos/{video_id}/media/{cap_id}/download")
    assert dl.status_code == 200
    vtt = dl.content.decode("utf-8")
    assert vtt.startswith("WEBVTT")
    assert "-->" in vtt

    # captions need text
    res = client.post(f"{API}/videos/{video_id}/captions", json={})
    assert res.status_code == 422

    # 4. enhance: auto colour + normalise + 9:16 framing + burn captions
    res = client.post(
        f"{API}/videos/{video_id}/media/{mid}/enhance",
        json={
            "normalize_audio": True,
            "auto_enhance": True,
            "framing": "9x16",
            "burn_captions": True,
        },
    )
    assert res.status_code == 202, res.text
    job_id = res.json()["job_id"]
    st = _wait_job(client, job_id)
    assert st["status"] == "done", st
    new_mid = st["result"]["media_id"]
    assert new_mid != mid
    assert st["result"]["report"]["summary"]["fail"] == 0

    # the enhanced artefact is a 720x1280 H.264 MP4
    dl = client.get(f"{API}/videos/{video_id}/media/{new_mid}/download")
    assert dl.status_code == 200
    data = dl.content
    assert data[4:8] == b"ftyp"
    probe = ffmpegx.probe_media(data)
    assert (probe.width, probe.height) == (720, 1280)
    assert probe.video_codec and "h264" in probe.video_codec

    # 5. MP3 audio export from the enhanced file
    res = client.post(f"{API}/videos/{video_id}/media/{new_mid}/export-audio")
    assert res.status_code == 201, res.text
    aud = [m for m in res.json()["media"] if m["kind"] == "audio"]
    assert len(aud) == 1
    dl = client.get(f"{API}/videos/{video_id}/media/{aud[0]['id']}/download")
    assert dl.status_code == 200
    assert dl.content[:3] == b"ID3" or dl.content[0] == 0xFF

    # 6. plain MP4 conversion of the original (no other changes)
    res = client.post(f"{API}/videos/{video_id}/media/{mid}/export-mp4")
    assert res.status_code == 202, res.text
    st2 = _wait_job(client, res.json()["job_id"])
    assert st2["status"] == "done", st2
    dl = client.get(f"{API}/videos/{video_id}/media/{st2['result']['media_id']}/download")
    assert dl.status_code == 200
    assert dl.content[4:8] == b"ftyp"

    # application payload now carries all media
    app_res = client.get(f"{API}/applications/{app_id}")
    assert app_res.status_code == 200
    video_out = app_res.json()["videos"][0]
    kinds = [m["kind"] for m in video_out["media"]]
    assert kinds.count("original") == 1
    assert kinds.count("enhanced") == 2
    assert kinds.count("captions") == 1
    assert kinds.count("audio") == 1

    # 7. delete the captions
    res = client.delete(f"{API}/videos/{video_id}/media/{cap_id}")
    assert res.status_code == 204
    res = client.get(f"{API}/videos/{video_id}/media/{cap_id}/download")
    assert res.status_code == 404


def _wait_trim_setup(client, video_id: str, test_clip: bytes) -> str:
    res = _upload(client, video_id, test_clip)
    assert res.status_code == 201, res.text
    return res.json()["media"][0]["id"]


def test_trim(client, app_video, test_clip):
    _, video_id, _ = app_video
    mid = _wait_trim_setup(client, video_id, test_clip)
    res = client.post(f"{API}/videos/{video_id}/media/{mid}/trim", json={"start": 1.0, "end": 4.0})
    assert res.status_code == 202, res.text
    st = _wait_job(client, res.json()["job_id"])
    assert st["status"] == "done", st
    dl = client.get(f"{API}/videos/{video_id}/media/{st['result']['media_id']}/download")
    assert dl.status_code == 200
    assert dl.content[4:8] == b"ftyp"
    probe = ffmpegx.probe_media(dl.content)
    assert 2.7 <= (probe.duration or 0) <= 3.4  # ~3s clip from a 6s source


def test_trim_validation(client, app_video, test_clip):
    _, video_id, _ = app_video
    mid = _wait_trim_setup(client, video_id, test_clip)
    res = client.post(f"{API}/videos/{video_id}/media/{mid}/trim", json={"start": 0, "end": 99})
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "BAD_TRIM_RANGE"
    res = client.post(f"{API}/videos/{video_id}/media/{mid}/trim", json={"start": 1, "end": 1.5})
    assert res.status_code == 422


def test_headshot_and_intro_card(client, app_video, test_clip):
    _, video_id, _ = app_video
    mid = _wait_trim_setup(client, video_id, test_clip)

    # headshot: generated PNG (no PIL needed)
    d = client  # placeholder to keep style
    import io as _io

    from app import ffmpegx as fx
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        from pathlib import Path

        hs = Path(td) / "head.png"
        fx.run_ffmpeg(
            ["-hide_banner", "-y", "-f", "lavfi", "-i", "color=c=0x3366aa:s=600x800",
             "-frames:v", "1", str(hs)]
        )
        data = hs.read_bytes()

    res = client.post(
        f"{API}/videos/{video_id}/media-headshot",
        files={"file": ("head.png", _io.BytesIO(data), "image/png")},
        data={"likeness_consent": "true"},
    )
    assert res.status_code == 201, res.text
    headshot = [m for m in res.json()["media"] if m["kind"] == "headshot"]
    assert len(headshot) == 1

    # headshot without likeness consent -> 422
    with tempfile.TemporaryDirectory() as td:
        hs2 = Path(td) / "head2.png"
        fx.run_ffmpeg(
            ["-hide_banner", "-y", "-f", "lavfi", "-i", "color=c=0xaa3366:s=600x800",
             "-frames:v", "1", str(hs2)]
        )
        data2 = hs2.read_bytes()
    res = client.post(
        f"{API}/videos/{video_id}/media-headshot",
        files={"file": ("head2.png", _io.BytesIO(data2), "image/png")},
        data={"likeness_consent": "false"},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "LIKENESS_CONSENT_REQUIRED"

    # intro card: name/role default from profile + CV (Thando / Support Team Lead)
    res = client.post(f"{API}/videos/{video_id}/intro-card", json={"seconds": 3})
    assert res.status_code == 202, res.text
    st = _wait_job(client, res.json()["job_id"], timeout_s=300)
    assert st["status"] == "done", st
    assert st["result"]["media_id"] and st["result"]["thumbnail_id"]

    dl = client.get(f"{API}/videos/{video_id}/media/{st['result']['media_id']}/download")
    assert dl.status_code == 200
    assert dl.content[4:8] == b"ftyp"
    probe = ffmpegx.probe_media(dl.content)
    assert 8.4 <= (probe.duration or 0) <= 9.6  # 3s intro + 6s clip

    dl = client.get(f"{API}/videos/{video_id}/media/{st['result']['thumbnail_id']}/download")
    assert dl.status_code == 200
    assert dl.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_intro_card_requires_headshot(client, app_video, test_clip):
    _, video_id, _ = app_video
    _wait_trim_setup(client, video_id, test_clip)
    res = client.post(f"{API}/videos/{video_id}/intro-card", json={})
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "NO_HEADSHOT"


def test_unknown_media_404(client, app_video):
    _, video_id, _ = app_video
    res = client.post(f"{API}/videos/{video_id}/media/does-not-exist/analyze")
    assert res.status_code == 404
    res = client.get(f"{API}/videos/{video_id}/media/does-not-exist/download")
    assert res.status_code == 404


def test_unknown_job_404(client):
    res = client.get(f"{API}/jobs/video/does-not-exist")
    assert res.status_code == 404


def test_enhance_without_captions_fails(client, app_video, test_clip):
    _, video_id, _ = app_video
    res = _upload(client, video_id, test_clip)
    media = res.json()["media"]
    res = client.post(
        f"{API}/videos/{video_id}/media/{media[0]['id']}/enhance",
        json={"burn_captions": True},
    )
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "NO_CAPTIONS"


# --- chunked upload (free-tier friendly) ---------------------------------------

def _chunk_init(client, video_id, data, consent=True, ct="video/webm", filename="take.webm"):
    return client.post(
        f"{API}/videos/{video_id}/upload-init",
        json={
            "filename": filename,
            "content_type": ct,
            "size": len(data),
            "likeness_consent": consent,
        },
    )


def _send_chunks(client, upload_id, data, chunk=5 * 1024 * 1024):
    offset = 0
    index = 0
    while offset < len(data):
        piece = data[offset:offset + chunk]
        r = client.post(
            f"{API}/uploads/{upload_id}/chunk?index={index}",
            content=piece,
        )
        assert r.status_code == 200, r.text
        offset += len(piece)
        index += 1


def _wait_upload_job(client, job_id, timeout=300):
    deadline = time.time() + timeout
    while time.time() < deadline:
        st = client.get(f"{API}/jobs/video/{job_id}").json()
        if st["status"] != "running":
            return st
        time.sleep(0.5)
    raise AssertionError("upload job did not finish in time")


def test_chunked_upload_roundtrip(client, app_video, test_clip):
    app_id, video_id, _ = app_video
    init = _chunk_init(client, video_id, test_clip)
    assert init.status_code == 201, init.text
    uid = init.json()["upload_id"]
    _send_chunks(client, uid, test_clip)
    res = client.post(f"{API}/uploads/{uid}/complete")
    assert res.status_code == 202, res.text
    st = _wait_upload_job(client, res.json()["job_id"])
    assert st["status"] == "done", st
    # media is stored against the video response
    app = client.get(f"{API}/applications/{app_id}").json()
    media = app["videos"][0]["media"]
    assert len(media) == 1
    assert media[0]["kind"] == "original"
    assert media[0]["duration"] and 5 < media[0]["duration"] < 8
    assert st["result"]["compressed"] is False, "small file stays as-is"


def test_chunked_upload_compresses_large_files(client, app_video, monkeypatch):
    import subprocess

    from app.api.v1 import studio as studio_mod

    # A near-lossless (CRF 4) clip: big, and guaranteed to shrink when
    # re-encoded at CRF 23 - like a real phone/recorder recording.
    import tempfile

    fd, clip_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    ffmpegx.run_ffmpeg(
        [
            "-hide_banner", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=6",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "4",
            "-pix_fmt", "yuv420p", "-c:a", "aac", clip_path,
        ],
        timeout=300,
    )
    test_clip = open(clip_path, "rb").read()
    os.unlink(clip_path)

    monkeypatch.setattr(studio_mod, "COMPRESS_THRESHOLD", 10_000)
    app_id, video_id, _ = app_video
    original_size = len(test_clip)
    init = _chunk_init(client, video_id, test_clip)
    uid = init.json()["upload_id"]
    _send_chunks(client, uid, test_clip)
    res = client.post(f"{API}/uploads/{uid}/complete")
    assert res.status_code == 202
    st = _wait_upload_job(client, res.json()["job_id"], timeout=600)
    assert st["status"] == "done", st
    assert st["result"]["compressed"] is True
    app = client.get(f"{API}/applications/{app_id}").json()
    media = app["videos"][0]["media"]
    assert len(media) == 1
    assert media[0]["content_type"] == "video/mp4"
    assert media[0]["size"] < original_size, "compressed file must be smaller"


def test_storage_usage_endpoint(client, app_video):
    app_id, video_id, _ = app_video
    app = client.get(f"{API}/applications/{app_id}").json()
    res = client.get(f"{API}/profiles/{app['profile_id']}/storage")
    assert res.status_code == 200
    body = res.json()
    assert body["video_media_count"] >= 0
    assert body["video_media_bytes"] >= 0
    assert "database_size" in body


def test_chunked_upload_requires_likeness_consent(client, app_video, test_clip):
    _, video_id, _ = app_video
    init = _chunk_init(client, video_id, test_clip, consent=False)
    assert init.status_code == 422
    assert init.json()["detail"]["code"] == "LIKENESS_CONSENT_REQUIRED"


def test_chunked_upload_rejects_bad_type(client, app_video, test_clip):
    _, video_id, _ = app_video
    init = _chunk_init(client, video_id, test_clip, ct="text/plain")
    assert init.status_code == 415


def test_chunked_upload_rejects_oversize(client, app_video, test_clip):
    _, video_id, _ = app_video
    init = client.post(
        f"{API}/videos/{video_id}/upload-init",
        json={"filename": "big.mp4", "content_type": "video/mp4",
              "size": 200 * 1024 * 1024, "likeness_consent": True},
    )
    assert init.status_code == 413


def test_chunked_upload_out_of_order_rejected(client, app_video, test_clip):
    _, video_id, _ = app_video
    uid = _chunk_init(client, video_id, test_clip).json()["upload_id"]
    r = client.post(f"{API}/uploads/{uid}/chunk?index=1", content=test_clip[:1024])
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "CHUNK_OUT_OF_ORDER"


def test_chunked_upload_incomplete_complete(client, app_video, test_clip):
    _, video_id, _ = app_video
    uid = _chunk_init(client, video_id, test_clip).json()["upload_id"]
    # send only half the bytes
    client.post(f"{API}/uploads/{uid}/chunk?index=0", content=test_clip[: len(test_clip) // 2])
    r = client.post(f"{API}/uploads/{uid}/complete")
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "INCOMPLETE"


def test_chunked_upload_unknown_session(client, app_video):
    res = client.post(f"{API}/uploads/does-not-exist/complete")
    assert res.status_code == 404
