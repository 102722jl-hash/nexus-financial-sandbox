(function(){
  const contract=window.NEXUS_V25_CONTRACT;
  const layers=[{id:'macro',title:'宏观 / 外部变量'},{id:'demand',title:'行业需求与价格'},{id:'route',title:'供给与生产路线'},{id:'constraint',title:'库存 / 产能约束'},{id:'chain',title:'产业价值池'},{id:'company',title:'关键公司'}];
  const scenarioDictionary={
    cokingCoalPrice:{label:'焦煤价格',patterns:['焦煤价格','焦煤','JM'],unit:'%',defaultValue:-20,outputLevel:'L2'},steelDemand:{label:'钢材终端需求',patterns:['钢材需求','钢铁需求'],unit:'%',defaultValue:-15,outputLevel:'L1'},minePolicy:{label:'煤矿供给政策',patterns:['煤矿供给','煤炭供给'],unit:'%',defaultValue:10,outputLevel:'L1'},scrapSupply:{label:'废钢供给',patterns:['废钢供给','废钢'],unit:'%',defaultValue:20,outputLevel:'L1'},rates:{label:'实际利率',patterns:['实际利率','利率'],unit:'%',defaultValue:10,outputLevel:'L1'}
  };
  const modelFamilies={DIVERSIFIED_MINER:{formula:'煤价 × 销量 + 电力与运输缓冲'},PURE_MINER:{formula:'煤价 × 销量 − 单位成本'},MIXED_MINER:{formula:'煤炭量价 + 煤化工组合 − 扩产'},INTEGRATED_STEEL:{formula:'钢材订单 − 焦煤成本 + 利用率'},SPECIAL_STEEL:{formula:'特钢订单 + 产品组合 − 原料成本'}};
  window.NEXUS_V25_DOMAIN={schemaVersion:'coal-steel-lab-1.0.0',id:'coal-steel',name:'焦煤—钢铁产业链',layers,scenarioDictionary,modelFamilies,evidencePolicy:{missingEvidenceStatus:'NEEDS_HUMAN_REVIEW',causalStatus:'ABSTAIN'},contractVersion:contract.schemaVersion};
}());
