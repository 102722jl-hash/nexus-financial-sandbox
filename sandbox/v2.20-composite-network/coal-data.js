(function(){
  const sources={
    mysql:{tier:'DATABASE_CANDIDATE',title:'MySQL workspace snapshot',url:'#mysql-snapshot',asOf:'2026-07-23'},
    postgres:{tier:'DATABASE_CANDIDATE',title:'PostgreSQL consolidated statements snapshot',url:'#postgres-snapshot',asOf:'2026-05-08'},
    model:{tier:'MODEL',title:'Coal-to-steel scenario assumptions',url:'#method',asOf:'prototype-1.0'}
  };
  const sourceNames={fact:'数据库候选值',premise:'数据库支持前提',model:'分析假设',result:'计算结果'};
  const layerNames={macro:'宏观 / 外部变量',demand:'行业需求与价格',route:'供给与生产路线',constraint:'库存 / 产能约束',chain:'产业价值池',company:'关键公司'};
  function node(id,label,sub,layer,x,y,size,sourceType,sourceId,description,editable=false){
    return{id,label,sub,layer,x,y,size,sourceType,sourceId,description,editable,unit:'相对基线变化 (%)',horizon:'未来 12 个月',baselineValue:100,dataCutoff:'2026-05-08'};
  }
  const nodes=[
    node('cokingCoalPrice','焦煤价格','JM.DCE', 'macro',.055,.16,19,'fact','mysql','焦煤连续合约价格情景。数据库快照值仅作候选输入，缺少原始来源闭环。',true),
    node('steelDemand','钢材终端需求','STEEL DEMAND','macro',.055,.38,14,'model','model','地产、基建、制造与出口需求的综合情景指数。',true),
    node('minePolicy','煤矿供给政策','MINE POLICY','macro',.055,.61,13,'model','model','安监、产能核增与进口政策的综合供给情景。',true),
    node('rates','实际利率','COST OF CAPITAL','macro',.055,.84,12,'model','model','融资成本与估值折现率情景。',true),

    node('coalRealization','煤炭实现售价','REALIZED COAL PRICE','demand',.205,.15,17,'model','model','期货价格向煤企实现售价的映射。'),
    node('steelRawCost','钢铁原料成本','RAW MATERIAL COST','demand',.205,.36,17,'model','model','焦煤价格向高炉钢铁原料成本的映射。'),
    node('steelOrders','钢材订单','STEEL ORDERS','demand',.205,.58,15,'model','model','终端需求向钢厂订单的映射。'),
    node('cokeDemand','焦化需求','COKE DEMAND','demand',.205,.81,13,'model','model','高炉开工对焦炭与焦煤的需求。'),

    node('mineVolume','煤炭销量','MINE VOLUME','route',.355,.16,14,'model','model','煤企在价格和政策约束下的销量响应。'),
    node('importSubstitution','进口替代','IMPORT MIX','route',.355,.38,13,'model','model','国内外焦煤价差变化引起的采购组合变化。'),
    node('bofRoute','高炉—转炉路线','BF-BOF','route',.355,.61,16,'model','model','对焦煤和焦炭依赖较高的钢铁生产路线。'),
    node('eafRoute','电炉替代路线','EAF / SCRAP','route',.355,.83,13,'model','model','废钢电炉对高炉路线的替代。'),

    node('mineHeadroom','煤矿供应余量','MINE HEADROOM','constraint',.505,.13,14,'model','model','有效供给相对需求的余量，不等同于名义产能。'),
    node('portInventory','港口库存','PORT INVENTORY','constraint',.505,.31,13,'model','model','港口与钢厂可用焦煤库存余量。'),
    node('cokeCapacity','焦化产能余量','COKE CAPACITY','constraint',.505,.50,13,'model','model','焦化装置相对需求的有效余量。'),
    node('steelUtilization','钢厂利用率','STEEL UTILIZATION','constraint',.505,.69,15,'model','model','订单与成本共同决定的钢厂开工利用率。'),
    node('scrapSupply','废钢供给','SCRAP SUPPLY','constraint',.505,.87,12,'model','model','电炉替代路线可获得的废钢供给。',true),

    node('coalMiningPool','煤炭开采价值池','COAL MINING','chain',.665,.13,17,'model','model','煤价、销量与单位成本共同形成的煤企价值池。'),
    node('cokingPool','焦化价值池','COKING','chain',.665,.31,13,'model','model','焦煤投入与焦炭售价共同形成的焦化价差。'),
    node('blastFurnacePool','普钢冶炼价值池','BLAST FURNACE STEEL','chain',.665,.50,16,'model','model','钢价、焦煤成本、销量与利用率共同形成的普钢价差。'),
    node('specialSteelPool','特钢价值池','SPECIAL STEEL','chain',.665,.69,15,'model','model','产品组合、订单与原料成本共同形成的特钢价差。'),
    node('downstreamPool','下游制造价值池','DOWNSTREAM','chain',.665,.87,12,'model','model','汽车、机械等制造业的钢材投入成本。'),

    node('shenhua','中国神华','601088.SH','company',.845,.10,17,'premise','postgres','煤炭、电力及运输综合经营暴露。'),
    node('shaanxi','陕西煤业','601225.SH','company',.845,.28,15,'premise','postgres','煤炭开采与销售经营暴露。'),
    node('yankuang','兖矿能源','600188.SH','company',.845,.46,15,'premise','postgres','煤炭、煤化工及海外业务经营暴露。'),
    node('baosteel','宝钢股份','600019.SH','company',.845,.66,16,'premise','postgres','普钢、板材与制造业客户经营暴露。'),
    node('citicsteel','中信特钢','000708.SZ','company',.845,.86,15,'premise','postgres','高端特钢产品组合经营暴露。')
  ];
  function edge(from,to,elasticity,lag,confidence,kind='model',note='分析弹性假设'){return{from,to,elasticity,lag,confidence,kind,note};}
  const edges=[
    edge('cokingCoalPrice','coalRealization',.78,.92,.52,'model','期货向煤企实现售价的传导率'),
    edge('cokingCoalPrice','steelRawCost',.62,.90,.52,'model','焦煤向高炉原料成本的传导率'),
    edge('steelDemand','steelOrders',.76,.92,.55),edge('steelDemand','cokeDemand',.42,.78,.48),
    edge('minePolicy','mineHeadroom',.64,.86,.48),edge('rates','steelOrders',-.18,.60,.40),
    edge('coalRealization','mineVolume',.18,.50,.38),edge('minePolicy','mineVolume',.36,.74,.42),
    edge('cokingCoalPrice','importSubstitution',-.24,.56,.36),edge('steelOrders','bofRoute',.66,.88,.50),
    edge('steelOrders','eafRoute',.24,.62,.40),edge('cokeDemand','cokeCapacity',-.46,.78,.42),
    edge('mineVolume','mineHeadroom',.38,.65,.38),edge('importSubstitution','portInventory',.42,.70,.38),
    edge('bofRoute','steelUtilization',.54,.84,.46),edge('eafRoute','steelUtilization',.22,.58,.36),
    edge('scrapSupply','eafRoute',.48,.76,.42),
    edge('coalRealization','coalMiningPool',.68,.91,.48),edge('mineVolume','coalMiningPool',.28,.72,.40),
    edge('mineHeadroom','coalMiningPool',-.12,.40,.32),edge('steelRawCost','cokingPool',-.30,.58,.35),
    edge('cokeDemand','cokingPool',.48,.76,.40),edge('steelRawCost','blastFurnacePool',-.52,.88,.48),
    edge('steelOrders','blastFurnacePool',.58,.90,.50),edge('steelUtilization','blastFurnacePool',.24,.72,.42),
    edge('steelRawCost','specialSteelPool',-.34,.72,.43),edge('steelOrders','specialSteelPool',.64,.91,.52),
    edge('steelRawCost','downstreamPool',-.22,.60,.36),
    edge('coalMiningPool','shenhua',.58,.88,.42),edge('coalMiningPool','shaanxi',.76,.92,.46),edge('coalMiningPool','yankuang',.68,.90,.44),
    edge('blastFurnacePool','baosteel',.72,.91,.48),edge('specialSteelPool','citicsteel',.74,.92,.50)
  ];
  const companies=[
    {id:'shenhua',ticker:'601088.SH',name:'中国神华',sourceId:'mysql',exposures:{coalMiningPool:.68,downstreamPool:.08},modelFamily:'DIVERSIFIED_MINER'},
    {id:'shaanxi',ticker:'601225.SH',name:'陕西煤业',sourceId:'mysql',exposures:{coalMiningPool:.86},modelFamily:'PURE_MINER'},
    {id:'yankuang',ticker:'600188.SH',name:'兖矿能源',sourceId:'mysql',exposures:{coalMiningPool:.75,cokingPool:.10},modelFamily:'MIXED_MINER'},
    {id:'baosteel',ticker:'600019.SH',name:'宝钢股份',sourceId:'mysql',exposures:{blastFurnacePool:.78,downstreamPool:.08},modelFamily:'INTEGRATED_STEEL'},
    {id:'citicsteel',ticker:'000708.SZ',name:'中信特钢',sourceId:'mysql',exposures:{specialSteelPool:.82},modelFamily:'SPECIAL_STEEL'}
  ];
  const interactions=[
    {a:'cokingCoalPrice',b:'steelDemand',target:'blastFurnacePool',coefficient:-.0018,label:'原料成本下降只有在订单稳定时才能充分转化为钢材价差'},
    {a:'minePolicy',b:'cokingCoalPrice',target:'coalMiningPool',coefficient:.0012,label:'供给政策与价格共同影响煤企量价组合'}
  ];
  const scenarioDefinitions=[
    {id:'cokingCoalPrice',patterns:['焦煤价格','焦煤','jm','炼焦煤'],label:'焦煤价格'},
    {id:'steelDemand',patterns:['钢材需求','钢铁需求','基建需求','地产需求'],label:'钢材终端需求'},
    {id:'minePolicy',patterns:['煤矿供给','安监','产能核增','煤炭供给'],label:'煤矿供给政策'},
    {id:'rates',patterns:['实际利率','利率','资本成本'],label:'实际利率'},
    {id:'scrapSupply',patterns:['废钢供给','废钢'],label:'废钢供给'}
  ];
  window.SANDBOX_DATA={sources,sourceNames,layerNames,nodes,edges,companies,interactions,scenarioDefinitions};
}());
