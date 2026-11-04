from datetime import datetime, timezone
import shutil

from fastapi.testclient import TestClient
import pytest

from factory import app as factory
from factory.media import run


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(factory, "ROOT", tmp_path)
    with TestClient(factory.app) as active:
        yield active


def test_dedup_and_early_approval(client):
    payload = {"topic": "Ollama"}
    job = client.post("/jobs", json=payload).json()
    assert job["verification"] == "UNVERIFIED"
    assert client.post("/jobs", json={"topic": "  ollama  "}).status_code == 409
    assert client.post(f"/jobs/{job['id']}/approve", json={
        "render_id": job["id"], "preview_reviewed": True, "facts_reviewed": True, "rights_reviewed": True,
    }).status_code == 409


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="FFmpeg tools required")
def test_real_ffmpeg_preview_blocks_missing_demo(client, monkeypatch):
    monkeypatch.setenv("FACTORY_VOICE", "mock")
    job = client.post("/jobs", json={"topic": "Ollama"}).json()
    url = f"/jobs/{job['id']}"
    sources = [{
        "url": "https://docs.ollama.com/api/generate", "title": "Ollama API",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "claim": "Fixture của kiểm thử phần mềm",
        "evidence": "Dữ liệu kiểm thử, không phải kết quả sử dụng sản phẩm.",
    }]
    scenes = [{
        "narration": "Hãy kiểm tra khả năng chạy mô hình trên máy của bạn.",
        "caption": "Kiểm tra trước khi cài đặt", "seconds": 16, "citations": [1],
    }] * 2
    assert client.put(url + "/editorial", json={"sources": sources, "scenes": scenes}).status_code == 200
    result = client.post(url + "/render").json()
    import time
    deadline = time.monotonic() + 90
    while result['state'] in {'QUEUED', 'RENDERING'} and time.monotonic() < deadline:
        time.sleep(.1)
        result = client.get(url).json()
    assert result["state"] == "QC_FAILED", result
    assert 30 <= result["duration"] <= 90
    assert any("demo" in issue for issue in result["issues"])
    assert any("mock" in issue for issue in result["issues"])
    assert "Kiểm tra" in client.get(url + "/artifacts/subtitles.srt").text
    assert client.get(url + "/artifacts/video.mp4", headers={"Range": "bytes=0-63"}).status_code == 206
    mp4 = factory.ROOT / job["id"] / result["render_id"] / "video.mp4"
    assert run("ffprobe", "-v", "error", "-select_streams", "v:0",
               "-show_entries", "stream=width,height", "-of", "csv=p=0", str(mp4)).strip() == "1080,1920"
    assert client.put(url + "/editorial", json={"sources": sources, "scenes": scenes}).status_code == 200
    assert client.get(url + "/artifacts/video.mp4").status_code == 404


def test_foundation_health_and_persistent_cancel(client):
    health = client.get("/health").json()
    assert health["status"] == "ok"
    assert health["schema_version"] == 3
    assert health["journal_mode"] == "wal"
    job = client.post("/jobs", json={"topic": "Foundation"}).json()
    url = f"/jobs/{job['id']}"
    assert client.post(url + "/cancel").json()["state"] == "CANCELLED"
    with TestClient(factory.app) as reopened:
        assert reopened.get(url).json()["state"] == "CANCELLED"
        assert reopened.post(url + "/render").status_code == 409


def test_migrate_unversioned_database(tmp_path):
    import sqlite3
    from contextlib import closing

    from factory.foundation import migrate

    with closing(sqlite3.connect(tmp_path / "legacy.db")) as db:
        with db:
            db.execute("CREATE TABLE jobs (id TEXT PRIMARY KEY, key TEXT UNIQUE, state TEXT, data TEXT)")
            db.execute("INSERT INTO jobs VALUES ('existing','topic','DISCOVERED','{}')")
        migrate(db)
        migrate(db)
        assert db.execute("PRAGMA user_version").fetchone() == (3,)
        assert db.execute("SELECT id,state FROM jobs").fetchone() == ("existing", "DISCOVERED")


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="FFmpeg tools required")
@pytest.mark.parametrize("format_name,width,height", [("short", 1080, 1920), ("long", 1920, 1080)])
def test_three_scene_renderer_with_audio(tmp_path, monkeypatch, format_name, width, height):
    tmp_path = tmp_path / "Giọng đọc Việt"
    tmp_path.mkdir()
    import json
    import subprocess
    import sys

    from factory.media import render

    # Generate a non-silent audio fixture through FFmpeg. This is a test tone,
    # so the result verifies muxing and timing without claiming voice quality.
    adapter = tmp_path / "fixture_tts.py"
    adapter.write_text(
        "import subprocess,sys\n"
        "subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',"
        "'sine=frequency=440:duration=11',sys.argv[4]],check=True)\n",
        encoding="utf-8",
    )
    from factory import media
    original_run = media.run

    def fixture_run(*args, **kwargs):
        if format_name == "long" and "h264_nvenc" in args:
            if args[-1] == "-":
                return ""
            raise subprocess.CalledProcessError(
                1, args, stderr="[h264_nvenc @ 1] OpenEncodeSessionEx failed"
            )
        if args[0] == "fixture-tts":
            return original_run(sys.executable, str(adapter), *args[1:], **kwargs)
        return original_run(*args, **kwargs)

    monkeypatch.setenv("FACTORY_ENCODER", "auto")
    monkeypatch.setenv("ESPEAK_BIN", "fixture-tts")
    monkeypatch.setattr(media, "run", fixture_run)
    scenes = [factory.Scene(narration=caption, caption=caption) for caption in
              ("Mở đầu", "Giải thích", "Kết luận")]
    assert render(tmp_path, scenes, format_name, "vi") == pytest.approx(33)
    probe = json.loads(run("ffprobe", "-v", "error", "-show_streams",
                           "-show_format", "-of", "json", str(tmp_path / "video.mp4")))
    video, audio = probe["streams"]
    assert (video["codec_name"], video["width"], video["height"]) == ("h264", width, height)
    assert video["pix_fmt"] == "yuv420p"
    assert audio["codec_name"] == "aac"
    technical = json.loads((tmp_path / "technical.json").read_text(encoding="utf-8"))
    assert not technical["black_intervals"]
    assert not technical["mostly_silent"]
    if format_name == "long":
        assert technical["encoder"] == "libx264"
    assert float(probe["format"]["duration"]) == pytest.approx(33, abs=0.25)
    assert (tmp_path / "thumbnail.jpg").stat().st_size > 0
    assert "Kết luận" in (tmp_path / "subtitles.srt").read_text(encoding="utf-8")



def test_cancel_running_child(tmp_path):
    import sys

    from factory import media

    marker = tmp_path / "started"
    token = media._checkpoint.set(lambda: cancel_if_started(marker))
    try:
        with pytest.raises(RuntimeError, match="cancel requested"):
            media.run(sys.executable, "-c",
                      "from pathlib import Path; import time; Path('started').touch(); "
                      "time.sleep(3); Path('survived').touch()", cwd=tmp_path, timeout=6)
    finally:
        media._checkpoint.reset(token)
    assert marker.exists()
    assert not (tmp_path / "survived").exists()


def cancel_if_started(marker):
    if marker.exists():
        raise RuntimeError("cancel requested")


@pytest.mark.parametrize("stderr,fallback", [
    ("[h264_nvenc @ 1] OpenEncodeSessionEx failed", True),
    ("Error opening input: Invalid data found", False),
])
def test_encoder_error_classification(monkeypatch, stderr, fallback):
    import subprocess

    from factory import media

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args, stderr=stderr)

    monkeypatch.setattr(media, "run", fail)
    expected = media.NvencFailure if fallback else subprocess.CalledProcessError
    with pytest.raises(expected):
        media.encode_scene("h264_nvenc", "ffmpeg")


@pytest.mark.parametrize("mode", ["corrupt", "cancel"])
def test_partial_mp4_never_published(tmp_path, monkeypatch, mode):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from factory import media

    partial = tmp_path / "video.partial.mp4"
    final = tmp_path / "video.mp4"
    written, inspected = Event(), Event()

    def fake_run(*args, **kwargs):
        if "concat" in args:
            partial.write_bytes(b"incomplete mp4")
            written.set()
            assert inspected.wait(5)
        if args[0] == "ffprobe":
            if partial.exists():
                raise ValueError("moov atom not found")
            return "2"
        return ""

    def checkpoint():
        if mode == "cancel" and inspected.is_set():
            raise RuntimeError("cancel requested")

    monkeypatch.setattr(media, "run", fake_run)
    monkeypatch.setenv("FACTORY_ENCODER", "cpu")
    scene = factory.Scene(narration="Kiểm tra", caption="Kiểm tra")
    with ThreadPoolExecutor() as pool:
        future = pool.submit(media.render, tmp_path, [scene], "short", "mock",
                             checkpoint=checkpoint)
        try:
            assert written.wait(5)
            assert partial.exists()
            assert not final.exists()
        finally:
            inspected.set()
        error = RuntimeError if mode == "cancel" else ValueError
        with pytest.raises(error):
            future.result(timeout=5)
    assert not partial.exists()
    assert not final.exists()


def test_current_render_approval_and_media_boundary(client):
    from contextlib import closing
    from uuid import uuid4

    job = client.post("/jobs", json={"topic": "Isolated approval fixture"}).json()
    render_id = str(uuid4())
    path = f"/jobs/{job['id']}"
    approval = dict(render_id=render_id, preview_reviewed=True, facts_reviewed=True, rights_reviewed=True)
    with closing(factory.connect()) as db, db:
        factory.write(db, job["id"], "QC_FAILED", {**job, "render_id": render_id, "issues": ["fixture"]})
    assert client.post(path + "/approve", json=approval).status_code == 409
    with closing(factory.connect()) as db, db:
        factory.write(db, job["id"], "AWAITING_APPROVAL", {**job, "render_id": render_id, "issues": []})
    assert client.post(path + "/approve", json={**approval, "render_id": str(uuid4())}).status_code == 409
    folder = factory.ROOT / job["id"] / render_id
    folder.mkdir(parents=True)
    audio = folder / "voice-0.wav"
    audio.write_bytes(b"invalid media")
    assert client.get(path + "/media/narration").status_code == 415
    audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
    assert client.get(path + "/media/narration").headers["content-type"] == "audio/wav"
    assert client.get(path + "/media/narration?scene=-1").status_code == 404
    assert client.get(path + "/media/demo").status_code == 404
    # Missing/incomplete artifacts cannot be approved even with a forged ready state.
    assert client.post(path + "/approve", json=approval).status_code == 409
    from factory.integrity import ARTIFACTS, binding
    for name in ARTIFACTS:
        (folder / name).write_bytes(b'isolated integrity fixture')
    with closing(factory.connect()) as db, db:
        current = factory.read(db, job['id'])
        current['render_binding'] = binding(folder, current)
        factory.write(db, job['id'], 'AWAITING_APPROVAL', current)
    assert client.post(path + "/approve", json=approval).status_code == 200
    assert client.get(path).json()["state"] == "APPROVED"
    assert client.put(path + "/editorial", json={"sources": [], "scenes": job["scenes"]}).status_code == 200
    assert client.post(path + "/approve", json=approval).status_code == 409
    assert client.get(path + "/media/narration").status_code == 404
