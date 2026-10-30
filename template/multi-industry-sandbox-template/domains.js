(function(){
  const layers=[
    {id:'macro',title:'宏观 / 外部变量',sub:'MACRO & EXTERNAL'},
    {id:'demand',title:'行业需求与价格',sub:'DEMAND & PRICE'},
    {id:'route',title:'供给与业务路线',sub:'SUPPLY & ROUTES'},
    {id:'constraint',title:'库存 / 资源约束',sub:'CONSTRAINTS'},
    {id:'chain',title:'产业价值池',sub:'VALUE POOLS'},
    {id:'company',title:'关键公司',sub:'COMPANIES'}
  ];
  const n=(id,label,layer,status='MATCHED',value=0,editable=false)=>({id,label,layer,status,value,editable});
  const e=(from,to,weight)=>({from,to,weight,evidenceClass:'ANALYST_ASSUMPTION'});
  const coal={
    id:'coal-steel',name:'焦煤—钢铁',version:'coal-steel-1.0.0',state:'MODEL PROTOTYPE',cutoff:'2026-07-23',currency:'CNY',scenario:{label:'焦煤价格',text:'焦煤价格下降 20%',node:'coalPrice',value:-20,min:-50,max:50},
    title:'焦煤价格如何沿煤炭—钢铁产业链传播',summary:'价格冲击穿过实现售价、原料成本、生产路线和产业价值池，最终进入公司经营与股权价值模型。',layers,
    nodes:[n('coalPrice','焦煤价格','macro','MATCHED',-20,true),n('steelDemand','钢材终端需求','macro','PARTIAL'),n('rates','实际利率','macro','PARTIAL'),n('coalRealized','煤炭实现售价','demand'),n('rawCost','钢铁原料成本','demand'),n('steelOrders','钢材订单','demand','PARTIAL'),n('mineVolume','煤炭销量','route'),n('bof','高炉—转炉','route'),n('eaf','电炉替代','route','UNAVAILABLE'),n('mineHeadroom','煤矿供给余量','constraint','PARTIAL'),n('inventory','港口库存','constraint','UNAVAILABLE'),n('utilization','钢厂利用率','constraint','PARTIAL'),n('coalPool','煤炭开采价值池','chain'),n('steelPool','普钢冶炼价值池','chain'),n('specialPool','特钢价值池','chain'),n('shenhua','中国神华','company'),n('shaanxi','陕西煤业','company'),n('baosteel','宝钢股份','company')],
    edges:[e('coalPrice','coalRealized',.78),e('coalPrice','rawCost',.62),e('steelDemand','steelOrders',.76),e('coalRealized','mineVolume',.18),e('steelOrders','bof',.66),e('rawCost','bof',-.24),e('mineVolume','mineHeadroom',-.30),e('bof','utilization',.54),e('coalRealized','coalPool',.68),e('mineVolume','coalPool',.28),e('rawCost','steelPool',-.52),e('steelOrders','steelPool',.58),e('rawCost','specialPool',-.34),e('steelOrders','specialPool',.64),e('coalPool','shenhua',.58),e('coalPool','shaanxi',.76),e('steelPool','baosteel',.72)],
    companies:[
      {id:'shenhua',ticker:'601088.SH',name:'中国神华',model:'综合煤企：煤炭量价 + 电力与运输缓冲',method:'EV / EBITDA',output:'L2 · NEEDS_HUMAN_REVIEW',market:{cap:684.2,date:'2026-07-23',status:'DATABASE_CANDIDATE'},baseline:{ebitda:82.0,multiple:7.9,netDebt:-41.0,nonOperating:12.0,minority:16.0},sensitivity:-.42,drivers:[['煤炭实现售价',-.54],['煤炭销量',-.08],['电力运输缓冲',.15]],evidence:[['当前市值','PARTIAL','股价日期可用，稀释股数待原始定位'],['合并财务','MATCHED','2025FY 数据库候选值'],['业务暴露','PARTIAL','缺少年报页级证据'],['估值倍数','ANALYST_ASSUMPTION','待建立可比公司样本']]},
      {id:'shaanxi',ticker:'601225.SH',name:'陕西煤业',model:'纯煤企：煤炭售价 × 销量 − 单位成本',method:'EV / EBITDA',output:'L2 · NEEDS_HUMAN_REVIEW',market:{cap:252.5,date:'2026-07-23',status:'DATABASE_CANDIDATE'},baseline:{ebitda:30.0,multiple:7.4,netDebt:-28.0,nonOperating:6.0,minority:2.0},sensitivity:-.67,drivers:[['煤炭实现售价',-.76],['煤炭销量',-.06],['单位成本刚性',-.10]],evidence:[['当前市值','PARTIAL','股本来源待确认'],['合并财务','MATCHED','2025FY 数据库候选值'],['业务暴露','PARTIAL','现货与长协比例待补'],['估值倍数','ANALYST_ASSUMPTION','周期调整待校准']]},
      {id:'baosteel',ticker:'600019.SH',name:'宝钢股份',model:'综合钢企：订单 − 原料成本 + 利用率',method:'EV / EBITDA',output:'L2 · NEEDS_HUMAN_REVIEW',market:{cap:147.1,date:'2026-07-23',status:'DATABASE_CANDIDATE'},baseline:{ebitda:27.5,multiple:5.8,netDebt:22.0,nonOperating:9.0,minority:4.0},sensitivity:.24,drivers:[['焦煤成本节省',.48],['钢材订单',0],['高炉利用率',0]],evidence:[['当前市值','PARTIAL','行情与股数需同日口径'],['合并财务','MATCHED','2025FY 数据库候选值'],['原料暴露','PARTIAL','焦煤成本占比待核验'],['估值倍数','ANALYST_ASSUMPTION','可比倍数尚未冻结']]}
    ],
    source:{type:'MySQL + PostgreSQL',tables:'28 行业 / 5,100 公司',financial:'5 家合并报表候选值',mapping:'13 MATCHED · 4 PARTIAL · 2 UNAVAILABLE'},
    mappings:[['焦煤期货收盘价','coalPrice','MATCHED'],['营业总收入','revenue','MATCHED'],['经营现金流净额','cfo','MATCHED'],['稀释后股数','dilutedShares','PARTIAL'],['长协销售占比','contractMix','UNAVAILABLE']],
    insight:'焦煤价格下降压低煤企实现售价，同时改善钢企原料成本；钢企是否最终受益仍取决于钢材订单是否稳定。'
  };
  const bank={
    id:'banking',name:'商业银行',version:'banking-template-0.1.0',state:'SCHEMA DEMO',cutoff:'2026-06-30',currency:'CNY',scenario:{label:'政策利率',text:'政策利率下降 25bp',node:'policyRate',value:-25,min:-100,max:100},
    title:'政策利率如何穿过银行资产负债表',summary:'利率变化进入资产收益率、存款成本、贷款需求与信用成本，再汇聚到净息差、利润和股权价值。',layers,
    nodes:[n('policyRate','政策利率','macro','MATCHED',-25,true),n('creditCycle','信用周期','macro','PARTIAL'),n('regulation','资本监管','macro','MATCHED'),n('loanDemand','贷款需求','demand','PARTIAL'),n('depositCost','存款成本','demand','PARTIAL'),n('assetYield','资产收益率','demand','PARTIAL'),n('corporate','对公信贷','route'),n('retail','零售信贷','route'),n('wealth','财富管理','route','UNAVAILABLE'),n('capital','资本充足率','constraint','MATCHED'),n('npl','不良率','constraint','MATCHED'),n('provision','拨备覆盖率','constraint','MATCHED'),n('nimPool','净息差价值池','chain'),n('feePool','非息收入价值池','chain','PARTIAL'),n('creditPool','信用成本价值池','chain'),n('cmb','招商银行','company'),n('icbc','工商银行','company'),n('citicbank','中信银行','company')],
    edges:[e('policyRate','assetYield',.72),e('policyRate','depositCost',.45),e('creditCycle','loanDemand',.64),e('loanDemand','corporate',.58),e('loanDemand','retail',.48),e('assetYield','nimPool',.70),e('depositCost','nimPool',-.62),e('retail','feePool',.28),e('creditCycle','npl',-.36),e('npl','creditPool',-.72),e('capital','corporate',.24),e('nimPool','cmb',.52),e('feePool','cmb',.30),e('nimPool','icbc',.66),e('creditPool','icbc',.24),e('nimPool','citicbank',.58),e('creditPool','citicbank',.28)],
    companies:[
      {id:'cmb',ticker:'600036.SH',name:'招商银行',model:'零售银行：生息资产 × 净息差 + 非息收入 − 信用成本',method:'P / B',output:'EXPOSURE_ONLY',market:{cap:null,date:null,status:'MARKET_CAP_DATA_MISSING'},baseline:null,sensitivity:-.18,drivers:[['净息差',-.30],['贷款需求',.08],['非息收入',0]],evidence:[['当前市值','UNAVAILABLE','示例领域未接入行情'],['财务底座','UNAVAILABLE','等待数据库映射'],['业务暴露','PARTIAL','模型家族候选'],['估值参数','UNAVAILABLE','ROE 与 P/B 框架待定义']]},
      {id:'icbc',ticker:'601398.SH',name:'工商银行',model:'大型银行：规模 × 净息差 − 信用成本 + 资本约束',method:'P / B',output:'EXPOSURE_ONLY',market:{cap:null,date:null,status:'MARKET_CAP_DATA_MISSING'},baseline:null,sensitivity:-.12,drivers:[['净息差',-.24],['贷款规模',.06],['信用成本',0]],evidence:[['当前市值','UNAVAILABLE','示例领域未接入行情'],['财务底座','UNAVAILABLE','等待数据库映射'],['业务暴露','PARTIAL','模型家族候选'],['估值参数','UNAVAILABLE','P/B 与 ROE 关系待校准']]},
      {id:'citicbank',ticker:'601998.SH',name:'中信银行',model:'对公银行：对公资产 × 净息差 − 信用成本',method:'P / B',output:'EXPOSURE_ONLY',market:{cap:null,date:null,status:'MARKET_CAP_DATA_MISSING'},baseline:null,sensitivity:-.15,drivers:[['净息差',-.26],['对公贷款',.07],['信用成本',0]],evidence:[['当前市值','UNAVAILABLE','示例领域未接入行情'],['财务底座','UNAVAILABLE','等待数据库映射'],['业务暴露','PARTIAL','模型家族候选'],['估值参数','UNAVAILABLE','可比样本待建立']]}
    ],
    source:{type:'领域包结构示例',tables:'未连接数据库',financial:'0 / 3',mapping:'8 MATCHED · 6 PARTIAL · 4 UNAVAILABLE'},
    mappings:[['政策利率','policyRate','MATCHED'],['资本充足率','capitalRatio','MATCHED'],['不良贷款率','nplRatio','MATCHED'],['净息差','netInterestMargin','PARTIAL'],['财富管理收入','wealthRevenue','UNAVAILABLE']],
    insight:'利率下降对银行并非单向利空：资产收益率与存款成本重定价速度不同，贷款需求和信用成本构成二阶抵消。'
  };
  window.DOMAIN_PACKAGES={layers,packages:[coal,bank]};
}());
