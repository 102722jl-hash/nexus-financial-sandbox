(function(){
  const data=window.SANDBOX_DATA;
  const timing={
    'macro>demand':{delay:0,ramp:3,persistence:12,decay:9,reversible:true},
    'macro>constraint':{delay:1,ramp:9,persistence:24,decay:18,reversible:false},
    'demand>route':{delay:1,ramp:6,persistence:12,decay:9,reversible:true},
    'route>constraint':{delay:1,ramp:9,persistence:18,decay:12,reversible:true},
    'demand>chain':{delay:1,ramp:6,persistence:12,decay:9,reversible:true},
    'route>chain':{delay:2,ramp:9,persistence:18,decay:12,reversible:true},
    'constraint>chain':{delay:2,ramp:9,persistence:18,decay:12,reversible:true},
    'chain>company':{delay:1,ramp:6,persistence:12,decay:9,reversible:true}
  };
  const edgeParameters=data.edges.map((edge,index)=>{
    const from=data.nodes.find((node)=>node.id===edge.from),to=data.nodes.find((node)=>node.id===edge.to);
    const spread=Math.max(.06,Math.abs(edge.elasticity)*.25);
    return{id:'EDGE-'+String(index+1).padStart(3,'0'),from:edge.from,to:edge.to,note:edge.note,low:edge.elasticity-spread,base:edge.elasticity,high:edge.elasticity+spread,confidence:edge.confidence,evidenceClass:'MODEL_ASSUMPTION',evidenceId:'EV-ANALYST-EDGE',invalidation:edge.note+'不再成立，或公司产品暴露与设定显著不同',...(timing[(from?.layer||'macro')+'>'+(to?.layer||'demand')]||{delay:1,ramp:9,persistence:18,decay:12,reversible:true})};
  });
  const companyModels={
    shenhua:{family:'DIVERSIFIED_MINER',label:'煤炭售价 × 销量 + 电力与运输缓冲',priceSensitivity:.54,volumeSensitivity:.20,marginLeverage:.44,capexResponse:.10,multipleDuration:.55},
    shaanxi:{family:'PURE_MINER',label:'煤炭售价 × 销量 − 单位成本',priceSensitivity:.76,volumeSensitivity:.18,marginLeverage:.60,capexResponse:.08,multipleDuration:.50},
    yankuang:{family:'MIXED_MINER',label:'煤炭量价 + 煤化工组合 − 扩产',priceSensitivity:.66,volumeSensitivity:.20,marginLeverage:.52,capexResponse:.14,multipleDuration:.58},
    baosteel:{family:'INTEGRATED_STEEL',label:'钢材销量 × 钢价 − 焦煤等原料成本',costPassThrough:.48,orderSensitivity:.45,marginLeverage:.42,capexResponse:.06,multipleDuration:.62},
    citicsteel:{family:'SPECIAL_STEEL',label:'特钢销量 × 产品组合 − 原料成本',costPassThrough:.30,orderSensitivity:.58,marginLeverage:.34,capexResponse:.04,multipleDuration:.68}
  };
  const evidenceRegistry={
    'EV-MYSQL-JM':{sourceId:'mysql',sourceTier:'DATABASE_CANDIDATE',statementClass:'CALCULATED_LINEAGE',temporalRole:'AS_OF_EVIDENCE',locatorStatus:'TABLE_ROW_IDENTIFIED',originalQuote:null,locator:'JM.DCE / TRADE_DT=20260723',snapshotSha256:null},
    'EV-PG-FINANCIAL':{sourceId:'postgres',sourceTier:'DATABASE_CANDIDATE',statementClass:'CALCULATED_LINEAGE',temporalRole:'AS_OF_EVIDENCE',locatorStatus:'QUERY_IDENTIFIED',originalQuote:null,locator:'statement_type=408001000 / report_period=20251231 / cutoff=20260508',snapshotSha256:null},
    'EV-ANALYST-EDGE':{sourceId:'model',sourceTier:'MODEL',statementClass:'ANALYST_ASSUMPTION',temporalRole:'NOT_APPLICABLE',locatorStatus:'NOT_APPLICABLE',originalQuote:null,locator:null,snapshotSha256:null}
  };
  const auditState={status:'NEEDS_HUMAN_REVIEW',formal_ready:false,causal:{status:'NOT_IDENTIFIED',causal_attribution_allowed:false,causal_conclusion:'ABSTAIN',method:null,gate_results:{},unmet_conditions:['缺少公司产品暴露的年报页级证据','传播参数尚未使用历史季度数据校准','缺少估值倍数与股价底座'],confounders:['钢材价格与终端需求','煤矿供给政策','公司产品组合与长协占比','宏观流动性'],counterevidence:['焦煤下跌可能由钢材需求转弱驱动，成本利好可能被订单下滑抵消'],boundary_zh:'本页面是条件情景模拟，不构成焦煤价格对公司价值的已识别因果结论。'}};
  window.SANDBOX_V2_CONFIG={schemaVersion:'coal-lab-model-1.0.0',edgeParameters,companyModels,evidenceRegistry,auditState};
}());
