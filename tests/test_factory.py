from datetime import datetime, timezone
import shutil

from fastapi.testclient import TestClient
import pytest

from factory import app as factory
from factory.media import run


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(factory, "ROOT", tmp_path)
    return TestClient(factory.app)


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
    assert health["schema_version"] == 1
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
        assert db.execute("PRAGMA user_version").fetchone() == (1,)
        assert db.execute("SELECT id,state FROM jobs").fetchone() == ("existing", "DISCOVERED")


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="FFmpeg tools required")
def test_three_scene_renderer_with_audio(tmp_path, monkeypatch):
    import json
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
        if args[0] == "fixture-tts":
            return original_run(sys.executable, str(adapter), *args[1:], **kwargs)
        return original_run(*args, **kwargs)

    monkeypatch.setenv("ESPEAK_BIN", "fixture-tts")
    monkeypatch.setattr(media, "run", fixture_run)
    scenes = [factory.Scene(narration=caption, caption=caption) for caption in
              ("Mở đầu", "Giải thích", "Kết luận")]
    assert render(tmp_path, scenes, "short", "vi") == pytest.approx(33)
    probe = json.loads(run("ffprobe", "-v", "error", "-show_streams",
                           "-show_format", "-of", "json", str(tmp_path / "video.mp4")))
    video, audio = probe["streams"]
    assert (video["codec_name"], video["width"], video["height"]) == ("h264", 1080, 1920)
    assert audio["codec_name"] == "aac"
    assert float(probe["format"]["duration"]) == pytest.approx(33, abs=0.25)
    assert (tmp_path / "thumbnail.jpg").stat().st_size > 0
    assert "Kết luận" in (tmp_path / "subtitles.srt").read_text(encoding="utf-8")
