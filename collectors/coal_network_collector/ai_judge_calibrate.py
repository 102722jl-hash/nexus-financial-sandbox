"""Automatic judgment mode and data-driven formula calibration.

AI_APPROVED is intentionally distinct from CONFIRMED: it enables automatic
classification while preserving whether a relationship has direct evidence.
"""
from __future__ import annotations
import json,math,sqlite3
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).parent; DB=ROOT/'coal_network.db'
def now(): return datetime.now(timezone.utc).isoformat()
def ensure(db):
    db.execute('''CREATE TABLE IF NOT EXISTS ai_judgements(judgement_id INTEGER PRIMARY KEY AUTOINCREMENT,object_type TEXT NOT NULL,object_id TEXT NOT NULL,decision TEXT NOT NULL,method TEXT NOT NULL,confidence REAL,reason TEXT NOT NULL,created_at TEXT NOT NULL)''')
def auto_approve_nodes(db):
    rows=db.execute("select node_id from network_nodes where status in ('AI_CANDIDATE','CANDIDATE')").fetchall(); n=0
    for (obj,) in rows:
        db.execute("update network_nodes set status='AI_APPROVED' where node_id=?",(obj,)); db.execute("insert into ai_judgements(object_type,object_id,decision,method,confidence,reason,created_at) values(?,?,?,?,?,?,?)",('NODE',obj,'AI_APPROVED','schema_metric_mapping',0.9,'指标来源和层级映射可由配置规则确定',now())); n+=1
    return n
def calibrate_edges(db):
    edges=db.execute("select edge_id,source_node_id,target_node_id,formula_id from network_edges where status in ('CANDIDATE','AI_CANDIDATE','AI_APPROVED')").fetchall(); approved=0; calibrated=0
    for eid,src,tgt,fid in edges:
        sm,sc=db.execute('select metric_code,entity_code from network_nodes where node_id=?',(src,)).fetchone(); tm,tc=db.execute('select metric_code,entity_code from network_nodes where node_id=?',(tgt,)).fetchone()
        source=db.execute("select as_of_date,value from metric_values where metric_code=? and entity_code is ? and value is not null",(sm,sc)).fetchall(); target=db.execute("select as_of_date,value from metric_values where metric_code=? and entity_code is ? and value is not null",(tm,tc)).fetchall(); left={d:v for d,v in source}; pairs=[(x,y) for d,x in left.items() for d2,y in target if d==d2]
        if len(pairs)>=3:
            xm=sum(x for x,y in pairs)/len(pairs); ym=sum(y for x,y in pairs)/len(pairs); den=sum((x-xm)**2 for x,y in pairs); slope=sum((x-xm)*(y-ym) for x,y in pairs)/den if den else 0.0; intercept=ym-slope*xm; params={'status':'AI_CALIBRATED','n':len(pairs),'slope':slope,'intercept':intercept,'lag_days':0,'method':'same_date_ols'}; state='AI_CALIBRATED'; conf=min(0.9,0.5+0.05*len(pairs)); calibrated+=1
        else:
            params={'status':'DATA_MISSING','n':len(pairs),'lag_days':0,'method':'insufficient_same_date_overlap'}; state='AI_ASSUMPTION'; conf=0.35
        db.execute("update formulas set parameters_json=?,parameter_status=?,status='AI_APPROVED' where formula_id=?",(json.dumps(params,ensure_ascii=False),state,fid)); db.execute("update network_edges set status='AI_APPROVED',parameter_status=?,confidence=? where edge_id=?",(state,conf,eid)); db.execute("insert into ai_judgements(object_type,object_id,decision,method,confidence,reason,created_at) values(?,?,?,?,?,?,?)",('EDGE',eid,'AI_APPROVED','historical_overlap_calibration',conf,'自动判断；缺少重叠样本时保留DATA_MISSING',now())); approved+=1
    return approved,calibrated
def close_reviews(db):
    db.execute("update review_queue set review_status='AI_APPROVED' where review_status='PENDING' and object_type in ('NODE','EDGE','FORMULA')")
def run(db):
    ensure(db); nodes=auto_approve_nodes(db); edges,calibrated=calibrate_edges(db); close_reviews(db); db.commit(); return {'nodes_ai_approved':nodes,'edges_ai_approved':edges,'formulas_ai_calibrated':calibrated}
if __name__=='__main__':
    db=sqlite3.connect(DB); print(json.dumps(run(db),ensure_ascii=False)); db.close()
