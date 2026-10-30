"""Idempotent graph builder; existing source-target relations are preserved."""
import hashlib,json,sqlite3
from pathlib import Path
from status_policy_v2 import USABLE_STATUSES,placeholders
ROOT=Path(__file__).parent
def sid(prefix,*parts): return prefix+hashlib.sha256('|'.join(parts).encode()).hexdigest()[:18]
def add(db,source,target,ftype,expr,relation,mechanism,sign=1):
    if db.execute("select 1 from network_edges where network_id='coal_power_v1' and source_node_id=? and target_node_id=?",(source,target)).fetchone(): return 0
    fid=sid('formula_',source,target,ftype); params=json.dumps({'status':'DATA_MISSING','sign':sign,'method':'requires_historical_calibration','causal_conclusion':'ABSTAIN'},ensure_ascii=False)
    db.execute("INSERT OR IGNORE INTO formulas(network_id,formula_id,formula_type,formula_expression,parameters_json,formula_version,parameter_status,lag_days,impact_cap_pct,invalidation_condition,status) VALUES(?,?,?,?,?,'2.0','AI_ASSUMPTION',0,0.25,?,'CANDIDATE')",('coal_power_v1',fid,ftype,expr,params,'历史样本不足或机制证据被推翻'))
    eid=sid('edge_',source,target,fid)
    db.execute("INSERT OR IGNORE INTO network_edges(network_id,edge_id,source_node_id,target_node_id,direction,relation_type,formula_id,formula_type,lag_days,impact_cap_pct,confidence,mechanism,parameter_status,evidence_source,parameters_json,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'CANDIDATE')",('coal_power_v1',eid,source,target,'FORWARD',relation,fid,ftype,0,0.25,0.5,mechanism,'AI_ASSUMPTION','AI_MECHANISM_CANDIDATE',params)); made=db.execute('select changes()').fetchone()[0]
    if made: db.execute("INSERT INTO review_queue(object_type,object_id,candidate_value,confidence,reason,evidence_ids,required_action,review_status,created_at) VALUES(?,?,?,?,?,?,?,'PENDING',datetime('now'))",('EDGE',eid,json.dumps({'source':source,'target':target,'formula':fid},ensure_ascii=False),0.5,'MECHANISM_TEMPLATE_CANDIDATE','[]','AI审核方向、机制、参数和证据'))
    return made
def build(db):
    rows=db.execute(f"select node_id,metric_code,entity_code from network_nodes where status in ({placeholders(USABLE_STATUSES)})",USABLE_STATUSES).fetchall(); by={(m,e):n for n,m,e in rows}; coal=[n for (m,e),n in by.items() if m in ('COAL_PRICE_5500','COAL_PRICE_5000') and e is None]; total=0
    for entity in sorted({e for _,e in by if e}):
        ops=[by[k] for k in (('POWER_GENERATION',entity),('GRID_SALES_POWER',entity),('ON_GRID_TARIFF',entity)) if k in by]
        revenue=by.get(('REVENUE',entity)); cost=by.get(('OPERATING_COST',entity)); profit=by.get(('NET_PROFIT',entity)); cash=by.get(('OPERATING_CASH_FLOW',entity)); close=by.get(('CLOSE_PRICE',entity))
        for c in coal:
            for op in ops: total+=add(db,c,op,'LINEAR_WEIGHT','output = input * weight','EXPOSURE','煤价与火电经营指标的候选暴露关系')
            if cost: total+=add(db,c,cost,'MARGIN_BRIDGE','cost_change = coal_price_change * exposure','COST_PRESSURE','煤价变化通过燃料成本影响营业成本')
        for metric in ('GRID_SALES_POWER','ON_GRID_TARIFF','POWER_GENERATION'):
            op=by.get((metric,entity))
            if op and revenue: total+=add(db,op,revenue,'REVENUE_BRIDGE','revenue = quantity * price','OPERATING_TO_FINANCIAL','经营量价指标到营业收入的候选桥接')
        if revenue and profit: total+=add(db,revenue,profit,'MARGIN_BRIDGE','profit = revenue - cost','ACCOUNTING_STRUCTURE','营业收入到净利润的会计候选桥接',1)
        if cost and profit: total+=add(db,cost,profit,'MARGIN_BRIDGE','profit = revenue - cost','ACCOUNTING_STRUCTURE','营业成本到净利润的会计候选桥接',-1)
        if profit and close: total+=add(db,profit,close,'PE_MULTIPLE','equity_value = earnings * pe_multiple','VALUATION_BRIDGE','净利润到市场估值代理的候选桥接')
        if cash and close: total+=add(db,cash,close,'DCF','equity_value = discounted_cash_flow','VALUATION_BRIDGE','经营现金流到市场估值代理的候选桥接')
    db.commit(); return total
if __name__=='__main__':
    db=sqlite3.connect(ROOT/'coal_network.db'); db.execute('pragma foreign_keys=on'); print('candidate_edges_created='+str(build(db))); db.close()
