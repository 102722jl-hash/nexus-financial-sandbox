"""Create immutable candidate package versions and atomically update a pointer."""
from __future__ import annotations
import argparse,hashlib,json,os,shutil,sqlite3,uuid
from datetime import datetime,timezone
from pathlib import Path
from export_package_v2 import export
from validate_v3 import validate

ROOT=Path(__file__).parent
VERSIONS=ROOT/'package_versions'
LATEST=ROOT/'latest_candidate.json'

def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def publish(db_path=ROOT/'coal_network.db'):
    validation=validate(db_path)
    if validation['errors'] or not validation['candidateReady']:
        return {'status':'NOT_PUBLISHED','reason':'CANDIDATE_GATE_FAILED','validation':validation}
    VERSIONS.mkdir(exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    version_id=f'coal_power_v1-{stamp}'
    staging=VERSIONS/f'.staging-{uuid.uuid4().hex}'
    final=VERSIONS/version_id
    try:
        package=export(db_path,staging)
        files={p.name:{'sha256':sha256(p),'bytes':p.stat().st_size} for p in sorted(staging.glob('*')) if p.is_file()}
        db=sqlite3.connect(db_path); cutoff=db.execute("select data_cutoff from network_registry where network_id='coal_power_v1'").fetchone()[0]; db.close()
        version_manifest={'versionId':version_id,'networkId':'coal_power_v1','createdAt':datetime.now(timezone.utc).isoformat(),'dataCutoff':cutoff,'candidateReady':True,'formalReady':validation['formalReady'],'validationWarnings':validation['warnings'],'files':files}
        manifest_path=staging/'version_manifest.json'; manifest_path.write_text(json.dumps(version_manifest,ensure_ascii=False,indent=2),encoding='utf-8'); version_manifest['files']['version_manifest.json']={'sha256':sha256(manifest_path),'bytes':manifest_path.stat().st_size}
        manifest_path.write_text(json.dumps(version_manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(staging,final)
        pointer={'versionId':version_id,'path':str(final),'dataCutoff':cutoff,'candidateReady':True,'formalReady':validation['formalReady'],'updatedAt':datetime.now(timezone.utc).isoformat(),'versionManifestSha256':sha256(final/'version_manifest.json')}
        temp=LATEST.with_name(f'.latest_candidate.{uuid.uuid4().hex}.tmp'); temp.write_text(json.dumps(pointer,ensure_ascii=False,indent=2),encoding='utf-8'); os.replace(temp,LATEST)
        return {'status':'PUBLISHED',**pointer,'fileCount':len(version_manifest['files'])}
    except Exception:
        if staging.exists(): shutil.rmtree(staging,ignore_errors=True)
        raise

def prune(keep=30):
    if not VERSIONS.exists(): return []
    versions=sorted((p for p in VERSIONS.iterdir() if p.is_dir() and not p.name.startswith('.staging-')),key=lambda p:p.name,reverse=True); removed=[]
    for path in versions[keep:]: shutil.rmtree(path); removed.append(str(path))
    return removed

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--db',default=str(ROOT/'coal_network.db')); p.add_argument('--keep',type=int,default=30); a=p.parse_args(); result=publish(Path(a.db)); result['pruned']=prune(a.keep) if result['status']=='PUBLISHED' else []; print(json.dumps(result,ensure_ascii=False,indent=2))
