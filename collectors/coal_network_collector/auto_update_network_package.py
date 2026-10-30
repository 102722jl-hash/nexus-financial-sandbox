"""Collect data and atomically publish the newest candidate network package."""
import argparse,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from candidate_package_publisher import publish,prune,verify_latest
ROOT=Path(__file__).parent
def main():
    p=argparse.ArgumentParser(); p.add_argument('--offline',action='store_true'); p.add_argument('--skip-market',action='store_true'); p.add_argument('--keep',type=int,default=30); a=p.parse_args(); cmd=[sys.executable,str(ROOT/'auto_collect_v2.py')]
    if a.offline: cmd.append('--offline')
    if a.skip_market: cmd.append('--skip-market')
    run=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace'); result={'pipelineVersion':'3.1-atomic-candidate-package','startedAt':datetime.now(timezone.utc).isoformat(),'collectionExitCode':run.returncode}
    if run.returncode: result.update({'status':'COLLECTION_FAILED','stdout':run.stdout[-4000:],'stderr':run.stderr[-4000:]})
    else:
        result['publication']=publish(ROOT/'coal_network.db'); result['verification']=verify_latest(); result['pruned']=prune(a.keep) if result['verification']['valid'] else []; result['status']='PUBLISHED' if result['publication']['status']=='PUBLISHED' and result['verification']['valid'] else 'PUBLICATION_FAILED'
    result['finishedAt']=datetime.now(timezone.utc).isoformat(); (ROOT/'auto_update_package_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(result,ensure_ascii=False,indent=2)); raise SystemExit(0 if result['status']=='PUBLISHED' else 1)
if __name__=='__main__': main()
