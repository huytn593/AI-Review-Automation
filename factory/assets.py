"""Bounded, content-validated imports with immutable provenance records."""
import asyncio
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from fastapi import HTTPException, Query, Request
from fastapi.responses import FileResponse
from .media import run
from .queue import audit

MAX_BYTES = 100_000_000
TYPES = {'.mp4': ('video', 'video/mp4'), '.webm': ('video', 'video/webm'),
         '.wav': ('audio', 'audio/wav'), '.mp3': ('audio', 'audio/mpeg'),
         '.png': ('image', 'image/png'), '.jpg': ('image', 'image/jpeg'), '.jpeg': ('image', 'image/jpeg')}


def inspect(path):
    suffix = path.suffix.lower()
    with path.open('rb') as stream:
        head = stream.read(16)
    valid = {'.mp4': head[4:8] == b'ftyp', '.webm': head.startswith(bytes.fromhex('1a45dfa3')),
             '.wav': head[:4] in {b'RIFF', b'RF64'} and head[8:12] == b'WAVE',
             '.mp3': head.startswith(b'ID3') or (len(head)>1 and head[0]==255 and head[1]&224==224),
             '.png': head.startswith(b'\x89PNG\r\n\x1a\n'),
             '.jpg': head.startswith(b'\xff\xd8\xff'), '.jpeg': head.startswith(b'\xff\xd8\xff')}
    if suffix not in TYPES or not valid.get(suffix):
        raise ValueError('Invalid file signature')
    probe = json.loads(run('ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe',
                          '-show_streams', '-show_format', '-of', 'json', str(path), timeout=15))
    kind, mime = TYPES[suffix]
    streams = probe.get('streams', [])
    if any(s.get('width', 0) > 8192 or s.get('height', 0) > 8192 for s in streams):
        raise ValueError('Media dimensions exceed limits')
    required = 'audio' if kind == 'audio' else 'video'
    if not any(s.get('codec_type') == required for s in streams):
        raise ValueError('Missing required media stream')
    if kind != 'image' and not 0 < float(probe.get('format', {}).get('duration', 0)) <= 7200:
        raise ValueError('Invalid or excessive media duration')
    return {'kind': kind, 'mime': mime,
            'duration': float(probe.get('format', {}).get('duration', 0)),
            'streams': [{k: s[k] for k in ('codec_type','codec_name','width','height') if k in s} for s in streams]}


def get_asset(db, job, asset_id):
    row = db.execute('SELECT data FROM media_assets WHERE id=? AND job=?', (str(asset_id), str(job))).fetchone()
    if row is None:
        raise HTTPException(404, 'Không tìm thấy media')
    return json.loads(row[0])


def install(app, root, connect, read):
    @app.get('/jobs/{job}/library')
    def listing(job: UUID):
        with closing(connect()) as db:
            read(db, job)
            return [json.loads(row[0]) for row in db.execute('SELECT data FROM media_assets WHERE job=? ORDER BY rowid DESC', (str(job),))]

    @app.post('/jobs/{job}/library', status_code=201)
    async def upload(job: UUID, request: Request, name: str = Query(min_length=1, max_length=180),
                     source: str = Query(min_length=1, max_length=500),
                     license: Literal['own', 'CC0', 'CC-BY', 'licensed'] = Query(),
                     commercial_rights: bool = Query()):
        if not commercial_rights:
            raise HTTPException(422, 'Cần xác nhận quyền sử dụng thương mại')
        suffix = Path(name).suffix.lower()
        if suffix not in TYPES or '/' in name or '\\' in name:
            raise HTTPException(422, 'Chỉ nhận MP4, WebM, WAV, MP3, PNG hoặc JPEG')
        with closing(connect()) as db:
            if read(db, job)['state'] in {'QUEUED','RENDERING','CANCELLING'}:
                raise HTTPException(409, 'Chờ render trước khi nhập media')
        folder = root() / str(job) / 'assets'
        folder.mkdir(parents=True, exist_ok=True)
        asset_id = str(uuid4())
        path = folder / (asset_id + suffix)
        size, digest = 0, hashlib.sha256()
        try:
            with path.open('xb') as stream:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise HTTPException(413, 'Media tối đa 100 MB')
                    stream.write(chunk)
                    digest.update(chunk)
            if not size:
                raise HTTPException(422, 'Tệp rỗng')
            try:
                details = await asyncio.to_thread(inspect, path)
            except Exception:
                raise HTTPException(422, 'Media hỏng hoặc không đọc được bằng FFprobe') from None
            item = {**details, 'id': asset_id, 'name': name, 'file': path.name,
                    'source': source, 'license': license, 'commercial_rights': commercial_rights,
                    'sha256': digest.hexdigest(), 'bytes': size,
                    'imported_at': datetime.now(timezone.utc).isoformat()}
            with closing(connect()) as db, db:
                db.execute('BEGIN IMMEDIATE')
                if read(db, job)['state'] in {'QUEUED','RENDERING','CANCELLING'}:
                    raise HTTPException(409, 'Dự án đã bắt đầu render; hãy nhập lại sau')
                existing = db.execute('SELECT data FROM media_assets WHERE job=? AND sha256=?', (str(job), item['sha256'])).fetchone()
                if existing:
                    path.unlink()
                    return {**json.loads(existing[0]), 'reused': True}
                db.execute('INSERT INTO media_assets VALUES (?,?,?,?)', (asset_id,str(job),item['sha256'],json.dumps(item,ensure_ascii=False)))
                audit(db, job, 'media_imported', {'asset_id': asset_id, 'sha256': item['sha256']})
            return item
        except BaseException:
            path.unlink(missing_ok=True)
            raise

    @app.get('/jobs/{job}/library/{asset_id}')
    def download(job: UUID, asset_id: UUID):
        with closing(connect()) as db:
            item = get_asset(db, job, asset_id)
        path = root() / str(job) / 'assets' / item['file']
        if not path.is_file():
            raise HTTPException(404, 'Tệp media bị thiếu')
        return FileResponse(path, media_type=item['mime'], headers={'X-Content-Type-Options':'nosniff'})
