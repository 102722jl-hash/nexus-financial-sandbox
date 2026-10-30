"""Build controlled candidate edges and formulas from metric nodes."""
import hashlib,json,sqlite3
from pathlib import Path
ROOT=Path(__file__).parent
def build(db):
    rows=db.execute("SELECT node_id,metric_code,entity_code,unit FROM network_nodes WHERE status='AI_CANDIDATE'").fetchall(); by={}
    for node,metric,entity,unit in rows: by.setdefault((metric,entity),[]).append((node,unit))
    prices=[x for (m,e),xs in by.items() if m.startswith('COAL_PRICE') for x in xs]; total=0
    for (metric,entity),targets in by.items():
        if metric not in {'POWER_GENERATION','GRID_SALES_POWER','ON_GRID_TARIFF'} or not entity: continue
        for src,uin in prices:
            target,uout=targets[0]; fid='f_'+hashlib.sha256((src+target).encode()).hexdigest()[:16]
            db.execute("INSERT OR IGNORE INTO formulas(network_id,formula_id,formula_type,formula_expression,parameters_json,formula_version,parameter_status,unit_in,unit_out,lag_days,impact_cap_pct,invalidation_condition,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",('coal_power_v1',fid,'LINEAR_WEIGHT','output = input * weight','{}','1.0','ANALYST_ASSUMPTION',uin,uout,0,0.25,'参数未校准','CANDIDATE'))
            eid='edge_'+hashlib.sha256((src+target+fid).encode()).hexdigest()[:18]
            db.execute("INSERT OR IGNORE INTO network_edges(network_id,edge_id,source_node_id,target_node_id,direction,relation_type,formula_id,formula_type,lag_days,impact_cap_pct,confidence,mechanism,parameter_status,evidence_source,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",('coal_power_v1',eid,src,target,'FORWARD','EXPOSURE',fid,'LINEAR_WEIGHT',0,0.25,0.5,'煤价到火电经营指标的候选传导','ANALYST_ASSUMPTION','CANDIDATE','CANDIDATE')); total+=1
            db.execute("INSERT INTO review_queue(object_type,object_id,candidate_value,confidence,reason,evidence_ids,required_action,created_at) VALUES(?,?,?,?,?,?,?,datetime('now'))",('EDGE',eid,json.dumps({'source':src,'target':target,'formula':fid},ensure_ascii=False),0.5,'MECHANISM_TEMPLATE_CANDIDATE','[]','确认方向、权重、滞后和证据'))
    db.commit(); return total
if __name__=='__main__':
    db=sqlite3.connect(ROOT/'coal_network.db'); print('candidate_edges='+str(build(db))); db.close()
