from contextlib import closing
from threading import Event
from uuid import uuid4
import time

import pytest
from fastapi.testclient import TestClient

from factory import app as factory
from factory.integrity import ARTIFACTS, binding
from factory.queue import claim, heartbeat


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(factory, 'ROOT', tmp_path)
    # No lifespan: claim processing explicitly to exercise worker fencing deterministically.
    return TestClient(factory.app)


def ready(client, topic='Queue fixture'):
    job = client.post('/jobs', json={'topic': topic}).json()
    return client.put('/jobs/' + job['id'] + '/editorial',
                      json={'sources': [], 'scenes': job['scenes']}).json()


def test_queue_survives_refresh_serializes_and_cancels(isolated):
    a, b = ready(isolated), ready(isolated, 'Second fixture')
    url = '/jobs/' + a['id']
    assert isolated.post(url + '/render').status_code == 202
    assert isolated.post(url + '/render').status_code == 409
    assert isolated.post('/jobs/' + b['id'] + '/render').status_code == 202
    assert TestClient(factory.app).get(url).json()['state'] == 'QUEUED'
    assert claim(factory.connect, factory.read, factory.write, 'first')[0] == a['id']
    assert claim(factory.connect, factory.read, factory.write, 'second') is None
    assert isolated.post('/jobs/' + b['id'] + '/cancel').json()['state'] == 'CANCELLED'
    assert isolated.post(url + '/cancel').json()['state'] == 'CANCELLING'
    with closing(factory.connect()) as db:
        rid = db.execute("SELECT id FROM render_queue WHERE job=?", (a['id'],)).fetchone()[0]
    with pytest.raises(RuntimeError, match='cancelled'):
        heartbeat(factory.connect, factory.read, a['id'], rid, 'first', Event())


def test_expired_worker_cannot_finish_or_renew(isolated):
    job = ready(isolated)
    url = '/jobs/' + job['id']
    pending = isolated.post(url + '/render').json()
    rid = pending['pending_render_id']
    claim(factory.connect, factory.read, factory.write, 'stale')
    with closing(factory.connect()) as db, db:
        db.execute('UPDATE render_queue SET lease_until=?', (time.time() - 1,))
    assert claim(factory.connect, factory.read, factory.write, 'new') is None
    assert isolated.get(url).json()['state'] == 'FAILED'
    with pytest.raises(RuntimeError, match='lease lost'):
        heartbeat(factory.connect, factory.read, job['id'], rid, 'stale', Event())
    assert isolated.post(url + '/render').status_code == 202
    assert claim(factory.connect, factory.read, factory.write, 'new')[1] != rid
    assert any(e['event'] == 'render_interrupted' for e in isolated.get(url + '/history').json())


def test_failed_retry_preserves_previous_complete_artifact(isolated, monkeypatch):
    job = ready(isolated)
    old = str(uuid4())
    folder = factory.ROOT / job['id'] / old
    folder.mkdir(parents=True)
    (folder / 'video.mp4').write_bytes(b'previous completed render')
    with closing(factory.connect()) as db, db:
        factory.write(db, job['id'], 'QC_FAILED', {**job, 'render_id': old})
    isolated.post('/jobs/' + job['id'] + '/render')
    item = claim(factory.connect, factory.read, factory.write, 'worker')
    monkeypatch.setattr(factory, 'render', lambda *args, **kwargs: (_ for _ in ()).throw(ValueError('fixture failure')))
    factory.execute_render(*item, 'worker', Event())
    current = isolated.get('/jobs/' + job['id']).json()
    assert current['state'] == 'FAILED'
    assert current['render_id'] == old
    assert (folder / 'video.mp4').read_bytes() == b'previous completed render'


@pytest.mark.parametrize('tamper', ['video.mp4', 'metadata.json', 'subtitles.srt', 'script'])
def test_approval_rejects_changed_content(isolated, tamper):
    job = ready(isolated)
    rid = str(uuid4())
    folder = factory.ROOT / job['id'] / rid
    folder.mkdir(parents=True)
    for name in ARTIFACTS:
        (folder / name).write_bytes(b'integrity test fixture')
    current = {**job, 'render_id': rid, 'issues': []}
    current['render_binding'] = binding(folder, current)
    if tamper == 'script':
        current['scenes'][0]['narration'] = 'Changed after QC'
    else:
        (folder / tamper).write_bytes(b'changed after QC')
    with closing(factory.connect()) as db, db:
        factory.write(db, job['id'], 'AWAITING_APPROVAL', current)
    assert isolated.post('/jobs/' + job['id'] + '/approve', json={
        'render_id': rid, 'preview_reviewed': True, 'facts_reviewed': True,
        'rights_reviewed': True,
    }).status_code == 409


def test_cross_origin_mutation_blocked(isolated):
    assert isolated.post('/jobs', json={'topic': 'Blocked'},
                         headers={'origin': 'https://evil.example'}).status_code == 403
    assert isolated.get('/jobs', headers={'host': 'evil.example'}).status_code == 403


def test_upgrade_backs_up_and_recovers_legacy_render(tmp_path, monkeypatch):
    import json
    import sqlite3
    monkeypatch.setattr(factory, 'ROOT', tmp_path)
    with closing(sqlite3.connect(tmp_path / 'jobs.db')) as db, db:
        db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY, key TEXT UNIQUE, state TEXT, data TEXT)')
        db.execute('PRAGMA user_version=1')
        db.execute('INSERT INTO jobs VALUES (?,?,?,?)', ('legacy','legacy','RENDERING',json.dumps({'topic':'Preserved'})))
    with closing(factory.connect()) as db:
        assert factory.read(db, 'legacy')['state'] == 'FAILED'
        assert factory.read(db, 'legacy')['topic'] == 'Preserved'
    backups=list((tmp_path/'backups').glob('*.db'))
    assert len(backups)==1
    with closing(sqlite3.connect(backups[0])) as db:
        assert db.execute('SELECT state FROM jobs').fetchone()==('RENDERING',)


def test_legacy_approval_is_retained_in_audit_but_not_trusted(tmp_path):
    import sqlite3
    import json
    from factory.foundation import migrate
    with closing(sqlite3.connect(tmp_path/'legacy.db')) as db, db:
        db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY, key TEXT UNIQUE, state TEXT, data TEXT)')
        db.execute('PRAGMA user_version=1')
        db.execute('INSERT INTO jobs VALUES (?,?,?,?)', ('old','old','APPROVED',json.dumps({'render_id':'preserved','approval':{'at':'old date'}})))
        db.commit()
        migrate(db)
        state,payload=db.execute('SELECT state,data FROM jobs').fetchone()
        assert state=='QC_FAILED'
        assert json.loads(payload)['render_id']=='preserved'
        assert 'approval' not in json.loads(payload)
        assert json.loads(db.execute('SELECT data FROM audit').fetchone()[0])['previous_approval']['at']=='old date'
