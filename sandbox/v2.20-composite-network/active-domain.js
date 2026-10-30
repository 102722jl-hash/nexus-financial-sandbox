(function(){
  const id=window.NEXUS_REQUESTED_DOMAIN;
  const coal=id==='coal-steel';
  if(!coal)window.NEXUS_ACTIVE_PACKAGE=window.NEXUS_V29_AI_PACKAGE;
  if(coal&&window.SANDBOX_ENGINE?.parseScenario){
    const parseScenario=window.SANDBOX_ENGINE.parseScenario.bind(window.SANDBOX_ENGINE);
    window.SANDBOX_ENGINE.parseScenario=(text)=>{
      const parsed=parseScenario(text);
      if(parsed.error)parsed.error='没有识别到可映射变量。请尝试输入焦煤价格、钢材需求、煤矿供给、废钢供给或实际利率。';
      return parsed;
    };
  }
  const aiDefaults={
    A:{name:'高端算力出口管制',text:'高端算力出口管制上升 50%',shocks:[{id:'exportControl',value:50,label:'出口管制强度'}]},
    B:{name:'政策与供给对照',text:'出口管制上升 50%，同时 HBM 供给增加 30%',shocks:[{id:'exportControl',value:50,label:'出口管制强度'},{id:'hbmSupply',value:30,label:'HBM 有效供给余量'}]}
  };
  const coalDefaults={
    A:{name:'焦煤价格下降',text:'焦煤价格下降 20%',shocks:[{id:'cokingCoalPrice',value:-20,label:'焦煤价格'}]},
    B:{name:'价格温和对照',text:'焦煤价格下降 10%',shocks:[{id:'cokingCoalPrice',value:-10,label:'焦煤价格'}]}
  };
  window.NEXUS_ACTIVE_RUNTIME={
    id,name:coal?'焦煤—钢铁产业链':'AI 基础设施产业链',shortName:coal?'煤炭—钢铁':'AI 基础设施',
    defaults:coal?coalDefaults:aiDefaults,
    selectedNode:coal?'cokingCoalPrice':'exportControl',selectedCompany:coal?'shenhua':'nvda',selectedEdge:'EDGE-001',
    caseTitle:coal?'焦煤价格下降如何穿过煤炭—钢铁产业链':'高端算力出口管制对上下游供需影响',
    caseDescription:coal?'改变焦煤价格，观察实现售价、原料成本、生产路线、经营指标、FCF 与公司市值如何逐层传导。':'改变政策变量，观察需求、技术路线、产能约束、产业链节点、公司经营与情景市值如何逐层传导。',
    presets:coal?[['焦煤价格下降 20%','焦煤 -20%'],['钢材需求下降 15%','钢材需求 -15%'],['煤矿供给增加 10%','煤矿供给 +10%'],['废钢供给增加 20%','废钢供给 +20%'],['实际利率上升 10%','利率 +10%']]:[['AI 资本开支下降 30%','AI CapEx -30%'],['HBM 供给增加 50%','HBM +50%'],['推理单位成本下降 70%','推理成本 -70%'],['出口管制上升 50%','出口管制 +50%'],['CoWoS 产能增加 40%','CoWoS +40%'],['电力供给下降 25%','电力 -25%']],
    stageLabels:coal?['情景输入','需求与价格','生产路线','库存与产能','产业价值池','公司暴露','财务桥接','市值重估']:['情景输入','需求驱动','技术路线','供给余量','产业价值池','公司暴露','财务桥接','市值重估'],
    database:coal?window.NEXUS_COAL_DB_SNAPSHOT:window.NEXUS_V28_DB_SNAPSHOT,
    financialBridge:coal?{fcfFormula:(item,fmt)=>'softClamp45(收入 '+fmt(item.revenue)+' × 0.32 + 利润率 '+fmt(item.margin)+' × 0.78 − CapEx '+fmt(item.capex)+' × 0.38) = '+fmt(item.fcf),revenueWhy:'公司专属量价、订单与成本驱动进入收入桥接；财务底座为数据库候选值，传播参数仍是分析假设。'}:{fcfFormula:(item,fmt)=>'softClamp60(收入 '+fmt(item.revenue)+' × 0.48 + 利润率 '+fmt(item.margin)+' × 0.72 − CapEx '+fmt(item.capex)+' × 0.42) = '+fmt(item.fcf),revenueWhy:'公司专属经营驱动进入收入桥接；当前数据库未覆盖该公司，因此不是已披露收入预测。'}
  };
}());
