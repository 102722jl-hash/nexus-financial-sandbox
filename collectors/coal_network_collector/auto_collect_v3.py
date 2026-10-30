"""Run V2 collection, then publish an immutable validated candidate package."""
import argparse,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from versioned_export import publish,prune
ROOT=Path(__file__).parent
def main():
    p=argparse.ArgumentParser(); p.add_argument('--offline',action='store_true'); p.add_argument('--skip-market',action='store_true'); p.add_argument('--keep',type=int,default=30); a=p.parse_args()
    cmd=[sys.executable,str(ROOT/'auto_collect_v2.py')]
    if a.offline: cmd.append('--offline')
    if a.skip_market: cmd.append('--skip-market')
    completed=subprocess.run(cmd,cwd=ROOT,check=False,capture_output=True,text=True,encoding='utf-8',errors='replace')
    result={'pipelineVersion':'3.0-versioned-candidate-packages','startedAt':datetime.now(timezone.utc).isoformat(),'collectionExitCode':completed.returncode}
    if completed.returncode!=0:
        result.update({'status':'COLLECTION_FAILED','stdout':completed.stdout[-4000:],'stderr':completed.stderr[-4000:]})
    else:
        result['publication']=publish(ROOT/'coal_network.db'); result['pruned']=prune(a.keep) if result['publication']['status']=='PUBLISHED' else []; result['status']=result['publication']['status']
    result['finishedAt']=datetime.now(timezone.utc).isoformat(); (ROOT/'auto_collect_v3_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(result,ensure_ascii=False,indent=2)); raise SystemExit(0 if result['status']=='PUBLISHED' else 1)
if __name__=='__main__': main()
