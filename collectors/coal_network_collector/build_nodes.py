"""Create candidate network nodes from accepted metric values."""
from __future__ import annotations
import hashlib,json,sqlite3
from pathlib import Path

ROOT=Path(__file__).parent
METRICS={
 'RAW_COAL_OUTPUT':(2,'原煤产量','flow'),'COAL_PRICE_5500':(3,'动力煤5500K价格','price'),
 'COAL_PRICE_5000':(3,'动力煤5000K价格','price'),'POWER_CONSUMPTION':(4,'全社会用电量','flow'),
 'THERMAL_CAPACITY':(4,'火电装机容量','stock'),'UTILIZATION_HOURS_THERMAL':(4,'火电利用小时','ratio'),
 'POWER_GENERATION':(4,'发电量','flow'),'GRID_SALES_POWER':(4,'上网电量','flow'),
 'ON_GRID_TARIFF':(4,'上网电价','price'),'INSTALLED_CAPACITY':(4,'装机容量','stock'),
 'REVENUE':(5,'营业收入','amount'),'OPERATING_COST':(5,'营业成本','amount'),
 'NET_PROFIT':(5,'归母净利润','amount'),'OPERATING_CASH_FLOW':(5,'经营现金流','amount'),
 'CLOSE_PRICE':(6,'收盘价','price')}

def build(db):
    rows=db.execute("SELECT metric_code,entity_code,unit,MAX(data_cutoff),MAX(evidence_id) FROM metric_values WHERE value_status='SOURCE_FACT' GROUP BY metric_code,entity_code,unit").fetchall(); created=0
    for code,entity,unit,cutoff,evidence in rows:
        if code not in METRICS: continue
        layer,name,mtype=METRICS[code]; entity_name=''
        if entity:
            found=db.execute("SELECT entity_name_cn FROM entities WHERE network_id='coal_power_v1' AND entity_code=?",(entity,)).fetchone(); entity_name=(found[0]+' · ') if found else entity+' · '
        node_id='node_'+hashlib.sha256(f'{code}|{entity or "INDUSTRY"}'.encode()).hexdigest()[:18]
        db.execute("INSERT OR IGNORE INTO network_nodes(network_id,node_id,layer_no,node_name_cn,node_description,node_type,metric_code,metric_name,metric_type,unit,editable,value_status,entity_code,evidence_id,data_cutoff,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",('coal_power_v1',node_id,layer,entity_name+name,'由已接受指标记录生成的候选节点','METRIC',code,name,mtype,unit,0,'SOURCE_FACT',entity,evidence,cutoff,'AI_CANDIDATE'))
        if db.execute('SELECT changes()').fetchone()[0]:
            db.execute("INSERT INTO review_queue(object_type,object_id,candidate_value,confidence,reason,evidence_ids,required_action,created_at) VALUES(?,?,?,?,?,?,? ,datetime('now'))",('NODE',node_id,json.dumps({'layer_no':layer,'name':entity_name+name},ensure_ascii=False),0.9,'DERIVED_FROM_ACCEPTED_METRIC',json.dumps([evidence]),'确认节点层级和名称')); created+=1
    db.commit(); return created
if __name__=='__main__':
    db=sqlite3.connect(ROOT/'coal_network.db'); db.execute('PRAGMA foreign_keys=ON'); print('created='+str(build(db))); db.close()
