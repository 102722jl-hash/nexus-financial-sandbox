(function(){
  const contract=window.NEXUS_V25_CONTRACT;
  const layers=[
    {id:'macro',title:'宏观 / 政策环境',nodeTypes:['rates','exportControl','powerSupply','itCycle','aiAdoption']},
    {id:'demand',title:'需求驱动',nodeTypes:['aiCapex','trainingDemand','inferenceCost','tokenDemand','sovereignDemand','dcBuildout']},
    {id:'route',title:'技术路线竞争',nodeTypes:['generalGpu','customAsic','domesticCompute','opticalScale','efficiency']},
    {id:'constraint',title:'供给余量 / 产能瓶颈',nodeTypes:['hbmSupply','cowosCapacity','waferCapacity','networkCapacity','transformerCapacity','coolingCapacity','constructionLabor']},
    {id:'chain',title:'产业链环节与节点',nodeTypes:['accelerators','memoryStack','foundryPackage','networkFabric','powerCooling','cloudServices','aiSoftware']},
    {id:'company',title:'公司',nodeTypes:['nvda','amd','avgo','tsmc','skhynix','micron','arista','vertiv','eaton','msft']}
  ];
  const scenarioDictionary={
    aiCapex:{label:'AI 资本开支',patterns:['AI 资本开支','AI CapEx','资本开支','capex'],unit:'相对基线变化',defaultValue:-30,outputLevel:'L3'},
    hbmSupply:{label:'HBM 有效供给余量',patterns:['HBM 供给','HBM capacity','高带宽存储'],unit:'供给余量指数变化 (%)',defaultValue:50,outputLevel:'L2'},
    inferenceCost:{label:'单位推理成本',patterns:['推理成本','成本 / Token','inference cost'],unit:'相对基线变化',defaultValue:-70,outputLevel:'L2'},
    exportControl:{label:'出口管制强度',patterns:['出口管制','出口限制','禁运'],unit:'相对基线变化',defaultValue:50,outputLevel:'L1'},
    cowosCapacity:{label:'CoWoS 可用产能余量',patterns:['CoWoS','先进封装','封装产能'],unit:'供给余量指数变化 (%)',defaultValue:40,outputLevel:'L2'},
    powerSupply:{label:'可用电力供给',patterns:['电力供给','可用电力','供电'],unit:'相对基线变化',defaultValue:-25,outputLevel:'L2'}
  };
  const modelFamilies={
    ACCELERATOR:{formula:'出货量 × ASP × 系统附加率',requiredDrivers:['volume','price','attach'],attributionMethod:'value_pressure_bridge'},
    MEMORY:{formula:'Bit 出货 × 价格 × HBM 组合 − 扩产',requiredDrivers:['bits','price','mix'],attributionMethod:'value_pressure_bridge'},
    FOUNDRY:{formula:'先进晶圆 + 先进封装 − 折旧 / CapEx',requiredDrivers:['wafer','packaging','utilization'],attributionMethod:'value_pressure_bridge'},
    ORDERS:{formula:'订单 + 积压转化 × 交付能力',requiredDrivers:['orders','backlog','delivery'],attributionMethod:'value_pressure_bridge'},
    CLOUD:{formula:'云收入 − AI CapEx − 折旧',requiredDrivers:['consumption','monetization','depreciation'],attributionMethod:'value_pressure_bridge'}
  };
  const evidencePolicy={sourceFacts:['T1','T2'],premiseSupport:['T1','T2','T3'],modelParameters:['ANALYST_ASSUMPTION','CALIBRATED_PARAMETER'],missingEvidenceStatus:'NEEDS_HUMAN_REVIEW',causalStatus:'ABSTAIN'};
  window.NEXUS_V25_DOMAIN={schemaVersion:'ai-infrastructure-1.0.0',id:'ai-infrastructure',name:'AI 基础设施产业链',layers,scenarioDictionary,modelFamilies,evidencePolicy,contractVersion:contract.schemaVersion};
}());
