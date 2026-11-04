"""Local, single-operator review workspace."""
from contextlib import closing, asynccontextmanager
from threading import Event, Thread, Lock
import time
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import shutil
from typing import Literal
from uuid import UUID, uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, HttpUrl

from .media import render
from .drafting import draft
from .foundation import diagnostics, migrate
from .integrity import binding, checksum
from .queue import audit, work, heartbeat
from . import settings as configuration
from .research import collect
from .tts import CommandTTS
from .media import run
from . import assets

load_dotenv()
ROOT = Path(os.getenv("FACTORY_DATA", "workspace")).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
@asynccontextmanager
async def lifespan(app):
    stop = Event()
    worker = Thread(target=work, args=(connect, read, write, execute_render, stop), daemon=True)
    worker.start()
    try:
        yield
    finally:
        stop.set()
        worker.join(timeout=12)


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def local_only(request: Request, call_next):
    from starlette.responses import PlainTextResponse
    host = request.headers.get("host", "").split(":")[0]
    origin = request.headers.get("origin")
    if host not in {"localhost", "127.0.0.1", "testserver"} or (
        origin and origin != f"{request.url.scheme}://{request.headers.get('host')}"
    ):
        return PlainTextResponse("Local workspace only", status_code=403)
    return await call_next(request)


def connect():
    db = sqlite3.connect(ROOT / "jobs.db", timeout=10)
    try:
        if db.execute("PRAGMA user_version").fetchone()[0] != 3:
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='jobs'").fetchone():
                backups = ROOT / 'backups'
                backups.mkdir(exist_ok=True)
                with closing(sqlite3.connect(backups / f'jobs-before-v3-{uuid4()}.db')) as backup:
                    db.backup(backup)
            db.execute("PRAGMA journal_mode=WAL")
            migrate(db)
    except Exception:
        db.close()
        raise
    return db


@app.exception_handler(sqlite3.OperationalError)
async def database_error(request: Request, exc: sqlite3.OperationalError):
    code = getattr(exc, "sqlite_errorcode", 0)
    if code & 0xff not in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
        raise exc
    return JSONResponse(
        {"detail": "Cơ sở dữ liệu đang bận. Hãy thử lại."},
        status_code=503,
        headers={"Retry-After": "2"},
    )


def read(db, job):
    row = db.execute("SELECT state,data FROM jobs WHERE id=?", (str(job),)).fetchone()
    if row is None:
        raise HTTPException(404, "Không tìm thấy dự án")
    return {"id": str(job), "state": row[0], **json.loads(row[1])}


class Source(BaseModel):
    url: HttpUrl
    title: str = Field(min_length=1, max_length=200)
    checked_at: datetime
    published_at: datetime | None = None
    claim: str = Field(min_length=1, max_length=300)
    evidence: str = Field(min_length=1, max_length=600)
    status: Literal["VERIFIED", "PARTIALLY_VERIFIED", "CONFLICTED", "UNVERIFIED", "OUTDATED"] = "UNVERIFIED"
    confidence_reason: str = Field(default="", max_length=600)


class Scene(BaseModel):
    narration: str = Field(min_length=1, max_length=450)
    caption: str = Field(min_length=1, max_length=100)
    seconds: float = Field(default=6, ge=1, le=20)
    citations: list[int] = Field(default_factory=list, max_length=10)
    visual_type: Literal["original_text_card", "demo"] = "original_text_card"


class Topic(BaseModel):
    topic: str = Field(min_length=2, max_length=100)
    format: Literal["short", "long"] = "short"


class Editorial(BaseModel):
    sources: list[Source] = Field(max_length=20)
    scenes: list[Scene] = Field(min_length=1, max_length=60)
    synthetic_disclosure_reviewed: bool = False


class Verification(BaseModel):
    scenario: str = Field(min_length=10, max_length=600)
    result: str = Field(min_length=10, max_length=600)
    recording_source: HttpUrl
    commercial_rights: Literal[True]
    asset_id: UUID | None = None


class Approval(BaseModel):
    render_id: UUID
    preview_reviewed: Literal[True]
    facts_reviewed: Literal[True]
    rights_reviewed: Literal[True]


FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@app.get("/assets/{filename}")
def frontend_asset(filename: str):
    from fastapi.staticfiles import StaticFiles

    assets = FRONTEND_DIST / "assets"
    static = StaticFiles(directory=assets, check_dir=False)
    path, stat = static.lookup_path(filename)
    if stat is None or not Path(path).is_file():
        raise HTTPException(404, "Asset not found")
    return FileResponse(path)


@app.get("/")
def home():
    build = FRONTEND_DIST / "index.html"
    return FileResponse(
        build if build.is_file() else Path(__file__).with_name("index.html"),
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/health")
def health():
    with closing(connect()) as db:
        version = db.execute("PRAGMA user_version").fetchone()[0]
        journal = db.execute("PRAGMA journal_mode").fetchone()[0]
        db.execute("SELECT id FROM jobs LIMIT 1").fetchone()
    return {"status": "ok", "schema_version": version, "journal_mode": journal,
            **diagnostics()}


@app.post("/jobs/{job}/cancel")
def cancel(job: UUID):
    with closing(connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        current = read(db, job)
        if current["state"] in {"CANCELLED", "CANCELLING"}:
            return current
        if current["state"] not in {"QUEUED", "RENDERING", "DISCOVERED", "SCRIPT_READY", "FAILED", "QC_FAILED"}:
            raise HTTPException(409, "Không thể hủy ở trạng thái hiện tại")
        if current["state"] == "QUEUED":
            db.execute("UPDATE render_queue SET state='CANCELLED' WHERE job=? AND state='QUEUED'", (str(job),))
            current.pop("pending_render_id", None)
        audit(db, job, "cancel_requested")
        write(db, job, "CANCELLING" if current["state"] == "RENDERING" else "CANCELLED", current)
    return get(job)


@app.get("/jobs")
def list_jobs():
    with closing(connect()) as db:
        return [read(db, row[0]) for row in db.execute("SELECT id FROM jobs ORDER BY rowid DESC LIMIT 100")]


@app.post("/jobs", status_code=201)
def create(topic: Topic):
    job = str(uuid4())
    data = {**topic.model_dump(), "verification": "UNVERIFIED", "sources": [],
            "scenes": [Scene(narration=f"Hôm nay mình tìm hiểu {topic.topic}.",
                             caption="Công cụ này làm được gì?").model_dump()]}
    with closing(connect()) as db, db:
        try:
            db.execute("INSERT INTO jobs VALUES (?,?,?,?)",
                       (job, " ".join(topic.topic.casefold().split()) + "|" + topic.format,
                        "DISCOVERED", json.dumps(data)))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "Chủ đề và định dạng đã tồn tại") from exc
    return get(job)


@app.get("/jobs/{job}")
def get(job: UUID):
    with closing(connect()) as db:
        return read(db, job)


def write(db, job, state, data):
    payload = {key: value for key, value in data.items() if key not in {"id", "state"}}
    db.execute("UPDATE jobs SET state=?,data=? WHERE id=?",
               (state, json.dumps(payload, ensure_ascii=False), str(job)))


@app.put("/jobs/{job}/editorial")
def edit(job: UUID, editorial: Editorial):
    with closing(connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        current = read(db, job)
        if current["state"] in {"QUEUED", "RENDERING", "CANCELLING", "CANCELLED"}:
            raise HTTPException(409, "Dự án đang dựng hoặc đã hủy")
        data = {key: current[key] for key in ("topic", "format", "verification", "demo") if key in current}
        data.update(editorial.model_dump(mode="json"))
        audit(db, job, "editorial_saved", {"approval_invalidated": bool(current.get("approval"))})
        write(db, job, "SCRIPT_READY", data)
    return get(job)


@app.post("/jobs/{job}/draft")
def suggest(job: UUID):
    current = get(job)
    if not current["sources"]:
        raise HTTPException(409, "Cần lưu nguồn trước khi tạo nháp")
    try:
        scenes = draft(current["topic"], current["format"], current["sources"], configuration.load(ROOT).ollama_model)
        editorial = Editorial(sources=current["sources"], scenes=scenes)
    except Exception as exc:
        raise HTTPException(422, f"Không tạo được nháp ({type(exc).__name__})") from exc
    return editorial.model_dump(mode="json")


@app.post('/jobs/{job}/scenes/{index}/rewrite')
def rewrite_scene(job: UUID, index: int):
    current = get(job)
    if not 0 <= index < len(current['scenes']):
        raise HTTPException(404, 'Không tìm thấy cảnh')
    if not current['sources'] or current['state'] in {'QUEUED','RENDERING','CANCELLING','CANCELLED'}:
        raise HTTPException(409, 'Cần nguồn đã lưu và dự án đang cho phép biên tập')
    try:
        scenes = draft(current['topic'], current['format'], current['sources'],
                       configuration.load(ROOT).ollama_model, scene=current['scenes'][index])
        if len(scenes) != 1:
            raise ValueError('Expected one scene')
        scene = Scene.model_validate(scenes[0])
        if not scene.citations or any(i < 1 or i > len(current['sources']) for i in scene.citations):
            raise ValueError('Invalid citations')
    except Exception as exc:
        raise HTTPException(422, f'Không viết lại được cảnh ({type(exc).__name__})') from None
    return scene.model_dump(mode='json')  # Draft only; the operator saves after review.


@app.put("/jobs/{job}/verification")
def verify(job: UUID, verification: Verification):
    # A local operator records and inspects this file before attesting.
    recording = ROOT / str(job) / "recording.webm"
    provenance = None
    if verification.asset_id:
        with closing(connect()) as db:
            provenance = assets.get_asset(db, job, verification.asset_id)
        if provenance['kind'] != 'video' or not provenance['commercial_rights']:
            raise HTTPException(422, 'Demo cần video có quyền sử dụng')
        recording = ROOT / str(job) / 'assets' / provenance['file']
    if not recording.is_file() or not 0 < recording.stat().st_size <= 100_000_000:
        raise HTTPException(409, "Cần recording.webm của phiên demo thực tế (tối đa 100 MB)")
    try:
        assets.inspect(recording)
        if provenance and checksum(recording) != provenance['sha256']:
            raise ValueError('Imported file changed')
    except Exception:
        raise HTTPException(422, 'Demo hỏng hoặc không đọc được bằng FFprobe') from None
    with closing(connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        current = read(db, job)
        if current["state"] in {"QUEUED", "RENDERING", "CANCELLING", "CANCELLED"}:
            raise HTTPException(409, "Dự án đang dựng hoặc đã hủy")
        demo_id = str(uuid4())
        filename = f'{demo_id}{recording.suffix}'
        shutil.copyfile(recording, ROOT / str(job) / filename)
        for key in ("render_id", "approval", "issues", "duration"):
            current.pop(key, None)
        current.update(verification="VERIFIED",
                       demo={**verification.model_dump(mode="json"), "file": filename, "provenance": provenance})
        audit(db, job, 'demo_verified', {'file': filename, 'asset_id': str(verification.asset_id) if verification.asset_id else None})
        write(db, job, "SCRIPT_READY", current)
    return get(job)


@app.post("/jobs/{job}/render", status_code=202)
def render_job(job: UUID):
    with closing(connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        current = read(db, job)
        if current["state"] not in {"SCRIPT_READY", "FAILED", "QC_FAILED"}:
            raise HTTPException(409, "Cần lưu kịch bản trước khi dựng")
        if current.get("render_attempts", 0) >= 3:
            raise HTTPException(409, "Đã thử 3 lần. Kiểm tra cấu hình và lưu lại kịch bản trước khi thử tiếp.")
        render_id = str(uuid4())
        current["pending_render_id"] = render_id
        current["render_attempts"] = current.get("render_attempts", 0) + 1
        current.pop("approval", None)
        db.execute("INSERT INTO render_queue(id,job,state,created) VALUES (?,?,'QUEUED',?)",
                   (render_id, str(job), time.time()))
        audit(db, job, "render_queued", {"render_id": render_id})
        write(db, job, "QUEUED", current)
    return get(job)


def execute_render(job, render_id, owner, stop):
    current = get(job)
    folder = ROOT / str(job) / render_id
    try:
        settings = configuration.load(ROOT).model_dump()
        voice = "mock" if os.getenv("FACTORY_VOICE") == "mock" else settings["voice"]
        folder.mkdir(parents=True)
        scenes = [Scene.model_validate(scene) for scene in current["scenes"]]
        demo = current.get("demo")
        demo_path = folder.parent / demo["file"] if demo else None
        def checkpoint():
            heartbeat(connect, read, job, render_id, owner, stop)

        duration = render(folder, scenes, current["format"], voice, demo_path, checkpoint, settings=settings)
        manifest = {"visuals": "original_text_cards", "music": None,
                    "voice": voice, "audio_settings": settings, "verification": current["verification"], "demo": demo}
        for name, data in {
            "research": current["sources"], "manifest": manifest,
            "metadata": {"title": current["topic"], "privacyStatus": "private",
                         "language": "vi", "source_urls": [s["url"] for s in current["sources"]]},
        }.items():
            (folder / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        issues = quality_issues(current, scenes, duration, voice)
        technical = json.loads((folder / "technical.json").read_text(encoding="utf-8"))
        if technical["black_intervals"]:
            issues.append("Phát hiện đoạn hình đen")
        if technical["mostly_silent"]:
            issues.append("Audio gần như im lặng")
        current["technical"] = technical
        checkpoint()
        current.update(render_id=render_id, duration=duration, issues=issues)
        current["render_binding"] = binding(folder, current)
        checkpoint()
        state = "QC_FAILED" if issues else "AWAITING_APPROVAL"
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception("Render failed for %s", job)
        shutil.rmtree(folder, ignore_errors=True)
        current = get(job)
        current["issues"] = [f"Lỗi dựng video ({type(exc).__name__}). Kiểm tra TTS, FFmpeg và media đầu vào."]
        state = "FAILED"
    with closing(connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        lease = db.execute("SELECT state,owner,lease_until FROM render_queue WHERE id=?", (render_id,)).fetchone()
        if not lease or lease[0] != "RUNNING" or lease[1] != owner or lease[2] < time.time():
            return  # A newer worker owns the job; this worker cannot publish its result.
        previous = read(db, job)
        if previous["state"] == "CANCELLING":
            shutil.rmtree(folder, ignore_errors=True)
            current = previous
            state = "CANCELLED"
        current.pop("pending_render_id", None)
        db.execute("UPDATE render_queue SET state=? WHERE id=?", (state, render_id))
        audit(db, job, "render_finished", {"render_id": render_id, "state": state})
        write(db, job, state, current)


def quality_issues(data, scenes, duration, voice):
    issues = []
    low, high = (30, 90) if data["format"] == "short" else (300, 600)
    if not low <= duration <= high:
        issues.append("Thời lượng ngoài giới hạn")
    sources = data["sources"]
    if not sources or any(not scene.citations or any(
        citation < 1 or citation > len(sources) for citation in scene.citations
    ) for scene in scenes):
        issues.append("Thiếu bằng chứng hoặc chỉ mục nguồn cho cảnh")
    if any(source.get("status") != "VERIFIED" or not source.get("confidence_reason", "").strip() for source in sources):
        issues.append("Có claim chưa được xác minh kèm giải thích")
    if data["verification"] != "VERIFIED" or not any(scene.visual_type == "demo" for scene in scenes):
        issues.append("Thiếu demo đã kiểm chứng và quyền sử dụng footage")
    if voice == "mock":
        issues.append("Âm thanh mock chỉ dùng để kiểm thử")
    if not data.get("synthetic_disclosure_reviewed"):
        issues.append("Chưa rà soát khai báo nội dung tổng hợp")
    return issues


@app.get("/jobs/{job}/artifacts/{name}")
def artifact(job: UUID, name: Literal["video.mp4", "thumbnail.jpg", "subtitles.srt",
                                      "timeline.json", "research.json", "manifest.json",
                                      "metadata.json"]):
    current = get(job)
    if "render_id" not in current:
        raise HTTPException(404, "Chưa có bản dựng")
    return FileResponse(ROOT / str(job) / current["render_id"] / name)


@app.get("/jobs/{job}/media/{kind}")
def media_preview(job: UUID, kind: Literal["demo", "narration"], scene: int = 0):
    current = get(job)
    directory = ROOT / str(job)
    if kind == "demo":
        filename = (current.get("demo") or {}).get("file", "")
        try:
            suffix = Path(filename).suffix
            if suffix not in {'.mp4', '.webm'}:
                raise ValueError('Invalid demo format')
            filename = f"{UUID(Path(filename).stem)}{suffix}"
        except ValueError:
            raise HTTPException(404, "Chưa có demo") from None
        target, mime = directory / filename, assets.TYPES[suffix][1]
    else:
        if not current.get("render_id") or not 0 <= scene < len(current["scenes"]):
            raise HTTPException(404, "Chưa có audio cho cảnh")
        target = directory / str(UUID(current["render_id"])) / f"voice-{scene}.wav"
        mime = "audio/wav"
    if not target.resolve().is_relative_to(directory) or not target.is_file():
        raise HTTPException(404, "Không tìm thấy media")
    with target.open("rb") as stream:
        header = stream.read(12)
    valid = (header[4:8] == b'ftyp' if target.suffix == '.mp4' else header.startswith(bytes.fromhex("1a45dfa3"))) if kind == "demo" else (
        header[:4] in {b"RIFF", b"RF64"} and header[8:12] == b"WAVE"
    )
    if not valid:
        raise HTTPException(415, "Định dạng media không hợp lệ")
    return FileResponse(target, media_type=mime, headers={"X-Content-Type-Options": "nosniff"})


@app.post("/jobs/{job}/approve")
def approve(job: UUID, approval: Approval):
    with closing(connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        current = read(db, job)
        if (current["state"] != "AWAITING_APPROVAL" or current["issues"]
                or current["render_id"] != str(approval.render_id)):
            raise HTTPException(409, "Bản dựng chưa đạt QC")
        try:
            actual = binding(ROOT / str(job) / current["render_id"], current)
        except (OSError, ValueError):
            raise HTTPException(409, "Artifact thiếu hoặc không hợp lệ; cần dựng lại") from None
        if actual != current.get("render_binding"):
            raise HTTPException(409, "Nội dung đã thay đổi sau QC; cần dựng lại")
        current["approval"] = {**approval.model_dump(mode="json"), **actual,
                               "at": datetime.now(timezone.utc).isoformat()}
        audit(db, job, "render_approved", current["approval"])
        write(db, job, "APPROVED", current)
    return get(job)


@app.get("/jobs/{job}/history")
def history(job: UUID):
    with closing(connect()) as db:
        read(db, job)
        return [{"event": event, "at": at, "data": json.loads(data)} for event, at, data in
                db.execute("SELECT event,at,data FROM audit WHERE job=? ORDER BY id DESC LIMIT 200", (str(job),))]


@app.get("/settings")
def get_settings():
    return configuration.load(ROOT).model_dump()


@app.put("/settings")
def update_settings(value: configuration.Settings):
    if (value.tts == "edge") != value.voice.startswith("vi-VN-"):
        raise HTTPException(422, "Giọng đọc không phù hợp với TTS provider")
    with closing(connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT 1 FROM jobs WHERE state IN ('QUEUED','RENDERING','CANCELLING')").fetchone():
            raise HTTPException(409, "Chờ render hoàn tất trước khi đổi cấu hình")
        configuration.save(ROOT, value)
    return get_settings()


@app.get("/discovery")
def discovery_cache():
    folder = ROOT / "research"
    snapshots = sorted(folder.glob("*.json"), reverse=True) if folder.exists() else []
    return json.loads(snapshots[0].read_text(encoding="utf-8")) if snapshots else {"items": [], "providers": []}


class Discover(BaseModel):
    query: str = Field(default="", max_length=100)


@app.post("/discovery")
def discover(payload: Discover):
    result = collect(payload.query)
    folder = ROOT / "research"
    folder.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    path = folder / f"{stamp}-{uuid4()}.json"
    temporary = path.with_suffix(".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
    return result


preview_lock = Lock()


class VoicePreview(BaseModel):
    text: str = Field(min_length=2, max_length=300)


@app.post("/voice-preview")
def voice_preview(payload: VoicePreview):
    if not preview_lock.acquire(blocking=False):
        raise HTTPException(409, "Đang tạo một bản nghe thử")
    folder = ROOT / "voice-previews" / str(uuid4())
    try:
        folder.mkdir(parents=True)
        settings = configuration.load(ROOT).model_dump()
        CommandTTS(run, settings['voice'], settings).synthesize(payload.text, folder / 'voice.wav', 6)
        duration = float(run('ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                             '-of', 'csv=p=0', str(folder / 'voice.wav')))
        if duration <= 0:
            raise ValueError('Empty voice preview')
        return {'url': '/voice-preview/' + folder.name, 'duration': duration}
    except Exception as exc:
        shutil.rmtree(folder, ignore_errors=True)
        raise HTTPException(422, f"TTS chưa hoạt động ({type(exc).__name__}). Kiểm tra provider, kết nối mạng và FFmpeg.") from None
    finally:
        preview_lock.release()


@app.get("/voice-preview/{preview}")
def preview_audio(preview: UUID):
    path = ROOT / 'voice-previews' / str(preview) / 'voice.wav'
    if not path.is_file():
        raise HTTPException(404, "Không tìm thấy bản nghe thử")
    return FileResponse(path, media_type='audio/wav', headers={'X-Content-Type-Options': 'nosniff'})


assets.install(app, lambda: ROOT, connect, read)
