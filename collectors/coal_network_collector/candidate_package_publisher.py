"""Publish immutable candidate packages with an atomic latest pointer."""
from __future__ import annotations
import hashlib,json,os,shutil,sqlite3,uuid
from datetime import datetime,timezone
from pathlib import Path
from export_package_v2 import export
from validate_v3 import validate
ROOT=Path(__file__).parent; VERSIONS=ROOT/'package_versions'; LATEST=ROOT/'latest_candidate.json'
def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''): h.update(block)
    return h.hexdigest()
def publish(db_path=ROOT/'coal_network.db'):
    gate=validate(db_path)
    if gate['errors'] or not gate['candidateReady']: return {'status':'NOT_PUBLISHED','reason':'CANDIDATE_GATE_FAILED','validation':gate}
    VERSIONS.mkdir(exist_ok=True); version_id='coal_power_v1-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'); staging=VERSIONS/f'.staging-{uuid.uuid4().hex}'; final=VERSIONS/version_id
    try:
        export(db_path,staging); files={p.name:{'sha256':sha256(p),'bytes':p.stat().st_size} for p in sorted(staging.glob('*')) if p.is_file()}
        db=sqlite3.connect(db_path); cutoff=db.execute("select data_cutoff from network_registry where network_id='coal_power_v1'").fetchone()[0]; db.close()
        vm={'versionId':version_id,'networkId':'coal_power_v1','createdAt':datetime.now(timezone.utc).isoformat(),'dataCutoff':cutoff,'candidateReady':True,'formalReady':gate['formalReady'],'validationWarnings':gate['warnings'],'files':files}; (staging/'version_manifest.json').write_text(json.dumps(vm,ensure_ascii=False,indent=2),encoding='utf-8'); os.replace(staging,final)
        pointer={'versionId':version_id,'path':str(final),'dataCutoff':cutoff,'candidateReady':True,'formalReady':gate['formalReady'],'updatedAt':datetime.now(timezone.utc).isoformat(),'versionManifestSha256':sha256(final/'version_manifest.json')}; temp=LATEST.with_name(f'.latest_candidate.{uuid.uuid4().hex}.tmp'); temp.write_text(json.dumps(pointer,ensure_ascii=False,indent=2),encoding='utf-8'); os.replace(temp,LATEST); return {'status':'PUBLISHED',**pointer,'dataFileCount':len(files)}
    except Exception:
        if staging.exists(): shutil.rmtree(staging,ignore_errors=True)
        raise
def verify_latest():
    if not LATEST.exists(): return {'valid':False,'errors':['LATEST_POINTER_MISSING']}
    pointer=json.loads(LATEST.read_text(encoding='utf-8')); folder=Path(pointer['path']); errors=[]
    manifest_path=folder/'version_manifest.json'
    if not manifest_path.exists(): return {'valid':False,'errors':['VERSION_MANIFEST_MISSING']}
    if sha256(manifest_path)!=pointer['versionManifestSha256']: errors.append('VERSION_MANIFEST_HASH_MISMATCH')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    for name,expected in manifest['files'].items():
        path=folder/name
        if not path.exists(): errors.append('FILE_MISSING:'+name)
        elif path.stat().st_size!=expected['bytes'] or sha256(path)!=expected['sha256']: errors.append('FILE_HASH_MISMATCH:'+name)
    return {'valid':not errors,'versionId':pointer['versionId'],'dataCutoff':pointer['dataCutoff'],'filesChecked':len(manifest['files']),'errors':errors}
def prune(keep=30):
    versions=sorted((p for p in VERSIONS.iterdir() if p.is_dir() and not p.name.startswith('.staging-')),key=lambda p:p.name,reverse=True) if VERSIONS.exists() else []; removed=[]
    for path in versions[keep:]: shutil.rmtree(path); removed.append(str(path))
    return removed
