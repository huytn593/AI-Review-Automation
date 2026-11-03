"""Local, single-operator review workspace."""
from contextlib import closing
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
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, HttpUrl

from .media import render
from .drafting import draft
from .foundation import diagnostics, migrate

load_dotenv()
ROOT = Path(os.getenv("FACTORY_DATA", "workspace")).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
app = FastAPI()


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
    db = sqlite3.connect(ROOT / "jobs.db")
    db.execute("PRAGMA journal_mode=WAL")
    try:
        if db.execute("PRAGMA user_version").fetchone()[0] != 1:
            migrate(db)
    except Exception:
        db.close()
        raise
    return db


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


class Approval(BaseModel):
    render_id: UUID
    preview_reviewed: Literal[True]
    facts_reviewed: Literal[True]
    rights_reviewed: Literal[True]


@app.get("/")
def home():
    return FileResponse(Path(__file__).with_name("index.html"))


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
        if current["state"] not in {"RENDERING", "DISCOVERED", "SCRIPT_READY", "FAILED", "QC_FAILED"}:
            raise HTTPException(409, "Không thể hủy ở trạng thái hiện tại")
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
        if current["state"] in {"RENDERING", "CANCELLING", "CANCELLED"}:
            raise HTTPException(409, "Dự án đang dựng hoặc đã hủy")
        data = {key: current[key] for key in ("topic", "format", "verification", "demo") if key in current}
        data.update(editorial.model_dump(mode="json"))
        write(db, job, "SCRIPT_READY", data)
    return get(job)


@app.post("/jobs/{job}/draft")
def suggest(job: UUID):
    current = get(job)
    if not current["sources"]:
        raise HTTPException(409, "Cần lưu nguồn trước khi tạo nháp")
    try:
        scenes = draft(current["topic"], current["format"], current["sources"])
        editorial = Editorial(sources=current["sources"], scenes=scenes)
    except Exception as exc:
        raise HTTPException(422, f"Không tạo được nháp ({type(exc).__name__})") from exc
    return editorial.model_dump(mode="json")


@app.put("/jobs/{job}/verification")
def verify(job: UUID, verification: Verification):
    # A local operator records and inspects this file before attesting.
    recording = ROOT / str(job) / "recording.webm"
    if not recording.is_file() or not 0 < recording.stat().st_size <= 100_000_000:
        raise HTTPException(409, "Cần recording.webm của phiên demo thực tế (tối đa 100 MB)")
    with closing(connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        current = read(db, job)
        if current["state"] in {"RENDERING", "CANCELLING", "CANCELLED"}:
            raise HTTPException(409, "Dự án đang dựng hoặc đã hủy")
        demo_id = str(uuid4())
        shutil.copyfile(recording, recording.with_name(f"{demo_id}.webm"))
        for key in ("render_id", "approval", "issues", "duration"):
            current.pop(key, None)
        current.update(verification="VERIFIED",
                       demo={**verification.model_dump(mode="json"), "file": f"{demo_id}.webm"})
        write(db, job, "SCRIPT_READY", current)
    return get(job)


@app.post("/jobs/{job}/render")
def render_job(job: UUID):
    with closing(connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        current = read(db, job)
        if current["state"] not in {"SCRIPT_READY", "FAILED", "QC_FAILED"}:
            raise HTTPException(409, "Cần lưu kịch bản trước khi dựng")
        if db.execute("SELECT 1 FROM jobs WHERE state IN ('RENDERING','CANCELLING')").fetchone():
            raise HTTPException(409, "Máy đang dựng một video khác")
        current.pop("render_id", None)
        write(db, job, "RENDERING", current)
    render_id = str(uuid4())
    folder = ROOT / str(job) / render_id
    voice = os.getenv("FACTORY_VOICE", "vi-VN-HoaiMyNeural" if os.getenv("FACTORY_TTS") == "edge" else "vi")
    try:
        folder.mkdir(parents=True)
        scenes = [Scene.model_validate(scene) for scene in current["scenes"]]
        demo = current.get("demo")
        demo_path = folder.parent / demo["file"] if demo else None
        def checkpoint():
            if get(job)["state"] == "CANCELLING":
                raise RuntimeError("Render cancelled")

        duration = render(folder, scenes, current["format"], voice, demo_path, checkpoint)
        manifest = {"visuals": "original_text_cards", "music": None,
                    "voice": voice, "verification": current["verification"], "demo": demo}
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
        current.update(render_id=render_id, duration=duration, issues=issues)
        state = "QC_FAILED" if issues else "AWAITING_APPROVAL"
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception("Render failed for %s", job)
        shutil.rmtree(folder, ignore_errors=True)
        current["issues"] = [f"Lỗi dựng video ({type(exc).__name__}): {exc}"]
        state = "FAILED"
    with closing(connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        if read(db, job)["state"] == "CANCELLING":
            shutil.rmtree(folder, ignore_errors=True)
            current.pop("render_id", None)
            state = "CANCELLED"
        write(db, job, state, current)
    return get(job)


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


@app.post("/jobs/{job}/approve")
def approve(job: UUID, approval: Approval):
    with closing(connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        current = read(db, job)
        if (current["state"] != "AWAITING_APPROVAL" or current["issues"]
                or current["render_id"] != str(approval.render_id)):
            raise HTTPException(409, "Bản dựng chưa đạt QC")
        current["approval"] = {**approval.model_dump(mode="json"),
                               "at": datetime.now(timezone.utc).isoformat()}
        write(db, job, "APPROVED", current)
    return get(job)
