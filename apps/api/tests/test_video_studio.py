"""Video Studio end-to-end: upload -> quality -> captions -> enhance -> exports.

A real 6s h264/aac test clip (test pattern + sine wave) is generated with
the bundled ffmpeg binary, so the whole pipeline runs for real -
including libx264 encoding, framing crops, loudness normalisation,
caption burn-in and MP3 extraction.
"""
import io
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
