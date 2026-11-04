from contextlib import closing
import shutil
import pytest
from fastapi.testclient import TestClient
from factory import app as factory, assets
from factory.media import run

@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(factory, 'ROOT', tmp_path/'data')
    factory.ROOT.mkdir()
    client=TestClient(factory.app)
    job=client.post('/jobs',json={'topic':'Media fixture'}).json()
    return client,job,tmp_path


def params(**patch):
    return {'name':'Demo tiếng Việt.mp4','source':'Original fixture','license':'own','commercial_rights':'true',**patch}


def test_upload_rejects_rights_traversal_corruption_and_oversize(workspace, monkeypatch):
    client,job,_=workspace
    url='/jobs/'+job['id']+'/library'
    assert client.post(url,params=params(commercial_rights='false'),content=b'abc').status_code==422
    assert client.post(url,params=params(name='../bad.mp4'),content=b'abc').status_code==422
    assert client.post(url,params=params(),content=b'<script>bad</script>').status_code==422
    monkeypatch.setattr(assets,'MAX_BYTES',16)
    assert client.post(url,params=params(),content=b'x'*17).status_code==413
    assert client.get(url).json()==[]
    assert list((factory.ROOT/job['id']/'assets').glob('*'))==[]


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='FFmpeg required')
def test_real_import_dedup_preview_verification_and_tamper(workspace):
    client,job,tmp=workspace
    clip=tmp/'Demo tiếng Việt.mp4'
    run('ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=green:s=320x180:r=24','-t','1','-c:v','libx264',str(clip))
    url='/jobs/'+job['id']
    first=client.post(url+'/library',params=params(),content=clip.read_bytes())
    assert first.status_code==201,first.text
    item=first.json()
    assert item['kind']=='video'
    again=client.post(url+'/library',params=params(),content=clip.read_bytes()).json()
    assert again['id']==item['id'] and again['reused']
    assert len(client.get(url+'/library').json())==1
    assert client.get(url+'/library/'+item['id'],headers={'Range':'bytes=0-20'}).status_code==206
    payload={'asset_id':item['id'],'scenario':'Recorded local fixture test','result':'Observed green frame in fixture',
             'recording_source':'https://example.com','commercial_rights':True}
    response=client.put(url+'/verification',json=payload)
    assert response.status_code==200,response.text
    assert response.json()['demo']['provenance']['sha256']==item['sha256']
    assert client.get(url+'/media/demo').headers['content-type']=='video/mp4'
    # The copied demo stays usable independently of the library import.
    imported=factory.ROOT/job['id']/'assets'/item['file']
    imported.write_bytes(b'changed')
    assert client.put(url+'/verification',json=payload).status_code==422
    assert client.get(url+'/media/demo').status_code==200
    other=client.post('/jobs',json={'topic':'Other project'}).json()
    assert client.get('/jobs/'+other['id']+'/library/'+item['id']).status_code==404


def test_import_is_locked_during_render(workspace):
    client,job,_=workspace
    with closing(factory.connect()) as db,db:
        factory.write(db,job['id'],'RENDERING',job)
    assert client.post('/jobs/'+job['id']+'/library',params=params(),content=b'bad').status_code==409
