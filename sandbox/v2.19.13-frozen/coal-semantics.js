(function(){
  const data=window.SANDBOX_DATA;
  const metricTypes={macro:'scenario_variable',demand:'price_or_demand_index',route:'production_route_index',constraint:'capacity_or_inventory_headroom',chain:'value_pool_index',company:'operating_exposure_index'};
  data.nodes.forEach((node)=>Object.assign(node,{
    metricType:metricTypes[node.layer],valueClass:node.editable?'ANALYST_ASSUMPTION':'CALCULATED_RESULT',
    displayRoleLabel:node.layer==='company'?'经营暴露指数':node.layer==='constraint'?'供给余量指数':'模型变化指数',
    unit:'相对基线变化 (%)',baselineValue:100,baselineUnit:'指数点',accountingPeriod:'SCENARIO_HORIZON',
    dataCutoff:node.id==='cokingCoalPrice'?'2026-07-23':'2026-05-08',currency:node.id==='cokingCoalPrice'?'CNY':null
  }));
  window.NEXUS_V26_SEMANTICS={schemaVersion:'coal-steel-node-semantics-1.0.0',definitions:metricTypes};
}());
