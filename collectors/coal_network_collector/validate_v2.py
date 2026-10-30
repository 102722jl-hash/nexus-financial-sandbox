"""Validate candidate usability and formal simulation readiness separately."""
import json,sqlite3
from datetime import date
from pathlib import Path
from manifest_v2 import build as build_manifest
ROOT=Path(__file__).parent
def validate(db_path=ROOT/'coal_network.db'):
    db=sqlite3.connect(db_path); errors=[]; warnings=[]
    required=['network_registry','network_layers','network_nodes','network_edges','entities','metric_values','formulas','evidence','valuation','review_queue']
    for table in required:
        if not db.execute("select 1 from sqlite_master where type='table' and name=?",(table,)).fetchone(): errors.append('MISSING_TABLE:'+table)
    for (eid,) in db.execute("select evidence_id from evidence where coalesce(source_url,'')='' or coalesce(original_quote,'')='' or coalesce(page_or_locator,'')='' or coalesce(published_at,'')='' "): errors.append('INCOMPLETE_EVIDENCE:'+eid)
    for (mid,) in db.execute("select m.metric_value_id from metric_values m join evidence e on e.evidence_id=m.evidence_id where e.source_tier in ('T3','T4') and m.value_status='SOURCE_FACT'"): errors.append('LOW_TIER_MARKED_SOURCE_FACT:'+mid)
    for edge,evidence in db.execute("select edge_id,evidence_id from network_edges where status='AI_APPROVED'"):
        if not evidence: warnings.append('AI_CANDIDATE_EDGE_WITHOUT_DIRECT_EVIDENCE:'+edge)
    for fid,pstatus in db.execute("select formula_id,parameter_status from formulas where status='AI_APPROVED'"):
        if pstatus not in ('AI_CALIBRATED','CALIBRATED_PARAMETER'): warnings.append('FORMULA_NOT_CALIBRATED:'+fid)
    errors += ['FOREIGN_KEY:'+str(x) for x in db.execute('pragma foreign_key_check').fetchall()]
    db.close(); manifest=build_manifest(db_path)
    if not manifest['candidateReady']: warnings.append('NO_CANDIDATE_COMPLETE_PATH')
    if not manifest['formalReady']: warnings.append('FORMAL_SIMULATION_NOT_READY')
    report={'errors':errors,'warnings':warnings,'candidateReady':manifest['candidateReady'],'formalReady':manifest['formalReady'],'packageStatus':manifest['packageStatus'],'manifest':'manifest.json'}
    (ROOT/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); return report
if __name__=='__main__': print(json.dumps(validate(),ensure_ascii=False,indent=2))
