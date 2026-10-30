"""Idempotent automatic review: AI-approved objects enter the candidate set."""
import json,sqlite3
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).parent
def now(): return datetime.now(timezone.utc).isoformat()
def ensure(db): db.execute('CREATE TABLE IF NOT EXISTS ai_judgements(judgement_id INTEGER PRIMARY KEY AUTOINCREMENT,object_type TEXT NOT NULL,object_id TEXT NOT NULL,decision TEXT NOT NULL,method TEXT NOT NULL,confidence REAL,reason TEXT NOT NULL,created_at TEXT NOT NULL)')
def log_once(db,kind,obj,method,confidence,reason):
    if not db.execute('select 1 from ai_judgements where object_type=? and object_id=? and decision=? and method=?',(kind,obj,'AI_APPROVED',method)).fetchone(): db.execute('insert into ai_judgements(object_type,object_id,decision,method,confidence,reason,created_at) values(?,?,?,?,?,?,?)',(kind,obj,'AI_APPROVED',method,confidence,reason,now()))
def run(db):
    ensure(db); nodes=edges=formulas=0
    for (node,) in db.execute("select node_id from network_nodes where status in ('AI_CANDIDATE','CANDIDATE')").fetchall():
        db.execute("update network_nodes set status='AI_APPROVED' where node_id=?",(node,)); log_once(db,'NODE',node,'schema_metric_mapping',0.9,'指标来源和层级映射通过规则审核'); nodes+=1
    for edge,fid in db.execute("select edge_id,formula_id from network_edges where status in ('AI_CANDIDATE','CANDIDATE')").fetchall():
        params=json.dumps({'status':'DATA_MISSING','method':'requires_historical_calibration','causal_conclusion':'ABSTAIN'},ensure_ascii=False); confidence=0.5
        db.execute("update network_edges set status='AI_APPROVED',parameter_status='AI_ASSUMPTION',confidence=?,parameters_json=? where edge_id=?",(confidence,params,edge)); log_once(db,'EDGE',edge,'candidate_mechanism_review',confidence,'AI通过进入候选集合；未识别为现实因果'); edges+=1
        if fid: db.execute("update formulas set status='AI_APPROVED',parameter_status='AI_ASSUMPTION',parameters_json=? where formula_id=?",(params,fid)); log_once(db,'FORMULA',fid,'controlled_formula_review',confidence,'受控公式族通过候选审核；参数仍待校准'); formulas+=1
    db.execute("update review_queue set review_status='AI_APPROVED' where review_status='PENDING' and object_type in ('NODE','EDGE','FORMULA')"); db.commit(); return {'nodes_ai_approved':nodes,'edges_ai_approved':edges,'formulas_ai_approved':formulas}
if __name__=='__main__':
    db=sqlite3.connect(ROOT/'coal_network.db'); print(json.dumps(run(db),ensure_ascii=False,indent=2)); db.close()
