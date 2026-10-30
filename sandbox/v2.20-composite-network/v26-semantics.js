(function(){
  const data=window.SANDBOX_DATA;
  const definitions={
    rates:{metricType:'rate_scenario_index',displayRoleLabel:'利率情景指数'},
    exportControl:{metricType:'policy_intensity_index',displayRoleLabel:'政策强度指数'},
    powerSupply:{metricType:'effective_supply_index',displayRoleLabel:'可用供给指数'},
    itCycle:{metricType:'demand_cycle_index',displayRoleLabel:'景气指数'},
    aiAdoption:{metricType:'adoption_index',displayRoleLabel:'渗透指数'},
    aiCapex:{metricType:'monetary_flow_index',displayRoleLabel:'资本开支指数'},
    trainingDemand:{metricType:'demand_flow_index',displayRoleLabel:'需求指数'},
    inferenceCost:{metricType:'price_index',displayRoleLabel:'单位成本指数'},
    tokenDemand:{metricType:'demand_flow_index',displayRoleLabel:'需求指数'},
    sovereignDemand:{metricType:'demand_flow_index',displayRoleLabel:'需求指数'},
    dcBuildout:{metricType:'activity_flow_index',displayRoleLabel:'建设活动指数'},
    generalGpu:{metricType:'route_demand_index',displayRoleLabel:'路线需求指数'},
    customAsic:{metricType:'route_demand_index',displayRoleLabel:'路线需求指数'},
    domesticCompute:{metricType:'route_demand_index',displayRoleLabel:'路线需求指数'},
    opticalScale:{metricType:'route_demand_index',displayRoleLabel:'路线需求指数'},
    efficiency:{metricType:'efficiency_index',displayRoleLabel:'效率指数'},
    hbmSupply:{label:'HBM 有效供给余量',sub:'HBM HEADROOM',metricType:'capacity_headroom_index',displayRoleLabel:'供给余量指数',description:'HBM 有效供给相对需求的余量。正值表示瓶颈缓解，负值表示供给趋紧；不等同于名义产能或收入。'},
    cowosCapacity:{label:'CoWoS 可用产能余量',sub:'PACKAGING HEADROOM',metricType:'capacity_headroom_index',displayRoleLabel:'供给余量指数',description:'先进封装可用产能相对需求的余量。正值可能来自扩产或需求下降，两者对供应商盈利的含义不同。'},
    waferCapacity:{label:'先进制程产能余量',sub:'WAFER HEADROOM',metricType:'capacity_headroom_index',displayRoleLabel:'供给余量指数',description:'先进制程晶圆可用产能相对需求的余量，不代表名义晶圆产能变化。'},
    networkCapacity:{label:'高速网络交付余量',sub:'NETWORK HEADROOM',metricType:'capacity_headroom_index',displayRoleLabel:'交付余量指数'},
    transformerCapacity:{label:'变压器 / 配电交付余量',sub:'POWER EQUIPMENT HEADROOM',metricType:'capacity_headroom_index',displayRoleLabel:'交付余量指数',description:'输配电设备交付能力相对订单需求的余量。负值表示瓶颈收紧，不代表工厂产能被削减。'},
    coolingCapacity:{label:'液冷交付余量',sub:'THERMAL HEADROOM',metricType:'capacity_headroom_index',displayRoleLabel:'交付余量指数',description:'液冷系统交付能力相对项目需求的余量。负值表示交付压力上升。'},
    constructionLabor:{label:'工程施工资源余量',sub:'LABOR HEADROOM',metricType:'capacity_headroom_index',displayRoleLabel:'资源余量指数',description:'工程施工资源相对项目需求的余量。负值表示资源更紧张。'},
    accelerators:{metricType:'value_pool_index',displayRoleLabel:'产业价值池指数'},
    memoryStack:{metricType:'value_pool_index',displayRoleLabel:'产业价值池指数'},
    foundryPackage:{metricType:'value_pool_index',displayRoleLabel:'产业价值池指数'},
    networkFabric:{metricType:'value_pool_index',displayRoleLabel:'产业价值池指数'},
    powerCooling:{metricType:'value_pool_index',displayRoleLabel:'产业价值池指数'},
    cloudServices:{metricType:'value_pool_index',displayRoleLabel:'产业价值池指数'},
    aiSoftware:{metricType:'value_pool_index',displayRoleLabel:'产业价值池指数'}
  };
  data.nodes.forEach((node)=>{
    const definition=definitions[node.id]||{};
    const isCompany=node.layer==='company';
    Object.assign(node,{
      metricType:isCompany?'operating_exposure_index':definition.metricType||'scenario_index',
      valueClass:node.editable?'ANALYST_ASSUMPTION':'CALCULATED_RESULT',
      displayRoleLabel:isCompany?'经营暴露指数':definition.displayRoleLabel||'模型变化指数',
      unit:'相对基线变化 (%)',baselineValue:100,baselineUnit:'指数点',
      accountingPeriod:'SCENARIO_HORIZON',dataCutoff:'NOT_SET',currency:null,
      ...definition
    });
  });
  data.scenarioDefinitions.forEach((item)=>{
    if(definitions[item.id]?.label)item.label=definitions[item.id].label;
  });
  window.NEXUS_V26_SEMANTICS={schemaVersion:'node-semantics-1.0.0',definitions};
}());
