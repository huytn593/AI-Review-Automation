"""Content-addressed approval bindings; no credentials or narration in audit logs."""
import hashlib
import json
from pathlib import Path

ARTIFACTS = ('video.mp4', 'subtitles.srt', 'timeline.json', 'research.json',
             'manifest.json', 'metadata.json', 'technical.json', 'thumbnail.jpg')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def checksum(path: Path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def binding(folder: Path, current: dict):
    files = {name: checksum(folder / name) for name in ARTIFACTS}
    if any((folder / name).stat().st_size == 0 for name in ARTIFACTS):
        raise ValueError('Empty render artifact')
    return {'job_id': current['id'], 'render_id': folder.name,
            'output_sha256': files['video.mp4'], 'artifacts_sha256': digest(files),
            'editorial_sha256': digest({key: current.get(key) for key in (
                'topic', 'format', 'sources', 'scenes', 'demo', 'verification',
                'synthetic_disclosure_reviewed')}),
            'metadata_sha256': files['metadata.json']}
