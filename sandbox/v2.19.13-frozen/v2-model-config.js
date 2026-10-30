(function () {
  const data = window.SANDBOX_DATA;
  const timingByTransition = {
    'macro>demand': { delay:0, ramp:9, persistence:30, decay:18, reversible:true },
    'demand>route': { delay:1, ramp:9, persistence:24, decay:18, reversible:true },
    'route>constraint': { delay:1, ramp:12, persistence:30, decay:24, reversible:false },
    'demand>constraint': { delay:2, ramp:10, persistence:30, decay:20, reversible:false },
    'constraint>chain': { delay:1, ramp:8, persistence:18, decay:15, reversible:true },
    'route>chain': { delay:1, ramp:9, persistence:24, decay:18, reversible:true },
    'demand>chain': { delay:2, ramp:10, persistence:24, decay:18, reversible:true },
    'chain>company': { delay:2, ramp:12, persistence:24, decay:18, reversible:true }
  };
  const criticalOverrides = {
    'exportControl>generalGpu': { low:-.66, base:-.48, high:-.34, delay:0, ramp:3, persistence:36, decay:24, reversible:false, confidence:.69, evidenceClass:'MODEL_ASSUMPTION', evidenceId:'EV-POLICY-BIS', invalidation:'许可范围、地区执行或产品分类与情景定义不一致' },
    'aiCapex>trainingDemand': { low:.46, base:.63, high:.79, delay:1, ramp:8, persistence:24, decay:15, reversible:true, confidence:.72, evidenceClass:'PREMISE_SUPPORT', evidenceId:'EV-MSFT-10K', invalidation:'资本开支变化仅反映付款节奏，而不是订单或部署变化' },
    'inferenceCost>tokenDemand': { low:-1.05, base:-.72, high:-.38, delay:1, ramp:15, persistence:36, decay:24, reversible:true, confidence:.55, evidenceClass:'MODEL_ASSUMPTION', evidenceId:'EV-MODEL-JEVONS', invalidation:'需求价格弹性不足，单位成本下降未转化为 Token 增长' },
    'hbmSupply>memoryStack': { low:.35, base:.66, high:.82, delay:2, ramp:9, persistence:18, decay:12, reversible:true, confidence:.66, evidenceClass:'MODEL_ASSUMPTION', evidenceId:'EV-HYNIX-IR', invalidation:'名义扩产未转化为有效良率、合格率或系统可交付量' },
    'cowosCapacity>accelerators': { low:.22, base:.39, high:.55, delay:3, ramp:12, persistence:30, decay:18, reversible:false, confidence:.69, evidenceClass:'MODEL_ASSUMPTION', evidenceId:'EV-TSMC-AR', invalidation:'先进封装扩产延期或与目标产品需求不匹配' },
    'powerSupply>dcBuildout': { low:.39, base:.62, high:.78, delay:2, ramp:18, persistence:36, decay:30, reversible:false, confidence:.72, evidenceClass:'PREMISE_SUPPORT', evidenceId:'EV-IEA-ELECTRICITY', invalidation:'自备电源、地域迁移或能效改善抵消公共电网约束' },
    'dcBuildout>powerCooling': { low:.38, base:.55, high:.71, delay:3, ramp:15, persistence:30, decay:24, reversible:false, confidence:.69, evidenceClass:'MODEL_ASSUMPTION', evidenceId:'EV-VRT-AR', invalidation:'建设计划未形成可执行订单或交付能力受限' },
    'accelerators>nvda': { low:.56, base:.72, high:.86, delay:1, ramp:8, persistence:18, decay:12, reversible:true, confidence:.75, evidenceClass:'MODEL_ASSUMPTION', evidenceId:'EV-NVDA-10K', invalidation:'产品组合、ASP 或竞争份额偏离模型假设' },
    'memoryStack>skhynix': { low:.49, base:.70, high:.88, delay:2, ramp:10, persistence:18, decay:12, reversible:true, confidence:.73, evidenceClass:'MODEL_ASSUMPTION', evidenceId:'EV-HYNIX-IR', invalidation:'HBM 产品组合与价格未按模型方向变化' },
    'foundryPackage>tsmc': { low:.52, base:.69, high:.84, delay:2, ramp:12, persistence:24, decay:18, reversible:false, confidence:.76, evidenceClass:'MODEL_ASSUMPTION', evidenceId:'EV-TSMC-AR', invalidation:'利用率、定价或先进封装收入组合偏离假设' },
    'networkFabric>arista': { low:.48, base:.66, high:.82, delay:2, ramp:11, persistence:24, decay:16, reversible:true, confidence:.73, evidenceClass:'MODEL_ASSUMPTION', evidenceId:'EV-ANET-AR', invalidation:'客户自研、交付限制或竞争改变订单转化率' },
    'powerCooling>vertiv': { low:.50, base:.68, high:.84, delay:3, ramp:14, persistence:30, decay:20, reversible:false, confidence:.74, evidenceClass:'MODEL_ASSUMPTION', evidenceId:'EV-VRT-AR', invalidation:'积压订单取消、项目延期或产能无法兑现' },
    'cloudServices>msft': { low:.31, base:.47, high:.61, delay:3, ramp:15, persistence:36, decay:24, reversible:true, confidence:.69, evidenceClass:'MODEL_ASSUMPTION', evidenceId:'EV-MSFT-10K', invalidation:'AI 使用量未形成可计费云收入或价格竞争加剧' }
  };
  function buildEdgeParameters() {
    return data.edges.map((edge,index) => {
      const from=data.nodes.find((node)=>node.id===edge.from), to=data.nodes.find((node)=>node.id===edge.to);
      const timing=timingByTransition[(from?.layer||'macro')+'>'+(to?.layer||'demand')]||{delay:1,ramp:12,persistence:24,decay:18,reversible:true};
      const spread=Math.max(.08,Math.abs(edge.elasticity)*.24);
      const defaults={low:edge.elasticity-spread,base:edge.elasticity,high:edge.elasticity+spread,confidence:edge.confidence,evidenceClass:edge.kind==='premise'?'PREMISE_SUPPORT':'MODEL_ASSUMPTION',evidenceId:edge.kind==='premise'?'EV-PREMISE-UNLOCATED':'EV-MODEL-ASSUMPTION',invalidation:edge.note||'传播弹性或方向偏离设定区间'};
      return {id:'EDGE-'+String(index+1).padStart(3,'0'),from:edge.from,to:edge.to,note:edge.note,...timing,...defaults,...(criticalOverrides[edge.from+'>'+edge.to]||{})};
    });
  }
  const companyModels = {
    nvda:{family:'ACCELERATOR',label:'出货量 × ASP × 系统附加率',weights:{volume:.54,price:.24,attach:.22},marginLeverage:.22,capexIntensity:.035,multipleDuration:1.25},
    amd:{family:'ACCELERATOR',label:'出货量 × ASP × 系统附加率',weights:{volume:.62,price:.18,attach:.20},marginLeverage:.18,capexIntensity:.045,multipleDuration:1.18},
    avgo:{family:'ORDERS',label:'定制订单 + 网络交付 − 产能摩擦',weights:{orders:.54,backlog:.28,delivery:.18},marginLeverage:.14,capexIntensity:.03,multipleDuration:1.05},
    skhynix:{family:'MEMORY',label:'Bit 出货 × 价格 × 组合 − 扩产',weights:{bits:.42,price:.34,mix:.24},marginLeverage:.36,capexIntensity:.18,multipleDuration:.58},
    micron:{family:'MEMORY',label:'Bit 出货 × 价格 × 组合 − 扩产',weights:{bits:.46,price:.31,mix:.23},marginLeverage:.32,capexIntensity:.16,multipleDuration:.62},
    tsmc:{family:'FOUNDRY',label:'晶圆 + 先进封装 − 折旧 / CapEx',weights:{wafer:.48,packaging:.36,utilization:.16},marginLeverage:.16,capexIntensity:.24,multipleDuration:.82},
    arista:{family:'ORDERS',label:'订单 + 积压转化 × 交付能力',weights:{orders:.49,backlog:.31,delivery:.20},marginLeverage:.13,capexIntensity:.025,multipleDuration:1.20},
    vertiv:{family:'ORDERS',label:'订单 + 积压转化 × 交付能力',weights:{orders:.44,backlog:.34,delivery:.22},marginLeverage:.17,capexIntensity:.05,multipleDuration:1.12},
    eaton:{family:'ORDERS',label:'订单 + 积压转化 × 交付能力',weights:{orders:.40,backlog:.36,delivery:.24},marginLeverage:.12,capexIntensity:.035,multipleDuration:.96},
    msft:{family:'CLOUD',label:'云收入 − AI CapEx − 折旧',weights:{consumption:.62,monetization:.38},marginLeverage:.08,capexIntensity:.38,depreciationLag:.32,multipleDuration:1.16}
  };
  const evidenceRegistry={
    'EV-POLICY-BIS':{sourceId:'policy',sourceTier:'T1',statementClass:'SOURCE_FACT',temporalRole:'AS_OF_EVIDENCE'},'EV-IEA-ELECTRICITY':{sourceId:'energy',sourceTier:'T1',statementClass:'PREMISE_SUPPORT',temporalRole:'POST_EVENT_VALIDATION'},'EV-MSFT-10K':{sourceId:'msft',sourceTier:'T2',statementClass:'PREMISE_SUPPORT',temporalRole:'AS_OF_EVIDENCE'},'EV-NVDA-10K':{sourceId:'nvda',sourceTier:'T2',statementClass:'PREMISE_SUPPORT',temporalRole:'AS_OF_EVIDENCE'},'EV-HYNIX-IR':{sourceId:'hynix',sourceTier:'T2',statementClass:'PREMISE_SUPPORT',temporalRole:'AS_OF_EVIDENCE'},'EV-TSMC-AR':{sourceId:'tsmc',sourceTier:'T2',statementClass:'PREMISE_SUPPORT',temporalRole:'AS_OF_EVIDENCE'},'EV-ANET-AR':{sourceId:'arista',sourceTier:'T2',statementClass:'PREMISE_SUPPORT',temporalRole:'AS_OF_EVIDENCE'},'EV-VRT-AR':{sourceId:'vertiv',sourceTier:'T2',statementClass:'PREMISE_SUPPORT',temporalRole:'AS_OF_EVIDENCE'},'EV-PREMISE-UNLOCATED':{sourceId:'model',sourceTier:'MODEL',statementClass:'PREMISE_SUPPORT',temporalRole:'UNVERIFIED'},'EV-MODEL-JEVONS':{sourceId:'model',sourceTier:'MODEL',statementClass:'MODEL_ASSUMPTION',temporalRole:'NOT_APPLICABLE'},'EV-MODEL-ASSUMPTION':{sourceId:'model',sourceTier:'MODEL',statementClass:'MODEL_ASSUMPTION',temporalRole:'NOT_APPLICABLE'}
  };
  Object.values(evidenceRegistry).forEach((item)=>Object.assign(item,{locatorStatus:item.sourceTier==='MODEL'?'NOT_APPLICABLE':'MISSING',originalQuote:null,locator:null,snapshotSha256:null}));
  const auditState={status:'NEEDS_HUMAN_REVIEW',formal_ready:false,causal:{status:'NOT_IDENTIFIED',causal_attribution_allowed:false,causal_conclusion:'ABSTAIN',method:null,gate_results:{},unmet_conditions:['缺少比较组与前趋势检验','缺少混杂因素控制与稳健性检验'],confounders:['宏观流动性','竞争产品周期','公司执行差异'],counterevidence:[],boundary_zh:'本工具输出结构化情景推演，不构成已识别的现实因果结论。'}};
  window.SANDBOX_V2_CONFIG={schemaVersion:'2.6.0-prototype',edgeParameters:buildEdgeParameters(),companyModels,evidenceRegistry,auditState};
}());
