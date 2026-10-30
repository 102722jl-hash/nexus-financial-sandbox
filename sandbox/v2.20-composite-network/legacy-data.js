(function () {
  const sources = {
    nvda: { tier: 'T2', title: 'NVIDIA FY2025 Form 10-K', url: 'https://investor.nvidia.com/financial-info/sec-filings-and-reports/default.aspx', asOf: 'FY2025' },
    amd: { tier: 'T2', title: 'AMD Annual Reports', url: 'https://ir.amd.com/financial-information/annual-reports-and-proxy-materials', asOf: 'FY2024' },
    avgo: { tier: 'T2', title: 'Broadcom SEC Filings', url: 'https://investors.broadcom.com/financial-information/sec-filings', asOf: 'FY2024' },
    tsmc: { tier: 'T2', title: 'TSMC Annual Reports', url: 'https://investor.tsmc.com/english/annual-reports', asOf: 'FY2024' },
    hynix: { tier: 'T2', title: 'SK hynix IR Library', url: 'https://www.skhynix.com/ir/UI-FR-IR03/', asOf: 'FY2024' },
    micron: { tier: 'T2', title: 'Micron SEC Filings', url: 'https://investors.micron.com/financials/sec-filings', asOf: 'FY2024' },
    arista: { tier: 'T2', title: 'Arista Annual Reports', url: 'https://investors.arista.com/financial-information/annual-reports-and-proxies', asOf: 'FY2024' },
    vertiv: { tier: 'T2', title: 'Vertiv Annual Reports', url: 'https://investors.vertiv.com/financials/annual-reports-and-proxies/default.aspx', asOf: 'FY2024' },
    eaton: { tier: 'T2', title: 'Eaton Annual Reports', url: 'https://www.eaton.com/us/en-us/company/investor-relations/financial-reports.html', asOf: 'FY2024' },
    msft: { tier: 'T2', title: 'Microsoft Annual Reports', url: 'https://www.microsoft.com/en-us/Investor/annual-reports.aspx', asOf: 'FY2025' },
    policy: { tier: 'T1', title: 'U.S. BIS advanced computing controls', url: 'https://www.bis.gov/press-release/commerce-strengthens-restrictions-advanced-computing-semiconductors', asOf: '公开规则' },
    rate: { tier: 'T1', title: 'Federal Reserve policy rates', url: 'https://www.federalreserve.gov/monetarypolicy/openmarket.htm', asOf: '动态数据' },
    energy: { tier: 'T1', title: 'IEA Electricity 2026', url: 'https://www.iea.org/reports/electricity-2026', asOf: '2026' },
    model: { tier: 'MODEL', title: 'NEXUS scenario assumptions', url: '#method', asOf: 'MVP 1.0' }
  };
  const sourceNames = { fact: '公开事实', premise: '事实支持前提', model: '模型假设', result: '情景结果' };
  const layerNames = { macro: '宏观 / 政策', demand: '需求驱动', route: '技术路线', constraint: '供给约束', chain: '产业链环节', company: '关键公司' };
  function node(id, label, sub, layer, x, y, size, sourceType, sourceId, description, editable) {
    return { id, label, sub, layer, x, y, size, sourceType, sourceId, description, editable: Boolean(editable), unit: '相对基线变化', horizon: '未来 12 个月' };
  }
  const nodes = [
    node('rates','实际利率','COST OF CAPITAL','macro',.055,.15,12,'fact','rate','实际利率通过融资门槛与估值折现率影响资本开支和长久期资产。',true),
    node('exportControl','出口管制强度','POLICY','macro',.055,.34,14,'fact','policy','高端算力及相关设备的贸易限制强度；本模型只模拟暴露变化，不判断政策效果。',true),
    node('powerSupply','可用电力供给','GRID CAPACITY','macro',.055,.54,15,'fact','energy','数据中心可获得的电力接入与输配电容量。',true),
    node('itCycle','企业 IT 景气','IT CYCLE','macro',.055,.73,11,'premise','model','企业软件、云和硬件预算的综合景气代理。',true),
    node('aiAdoption','AI 应用渗透','ADOPTION','macro',.055,.90,12,'premise','model','企业与消费者工作流采用生成式 AI 的速度。',true),
    node('aiCapex','云厂商 AI 资本开支','HYPERSCALER CAPEX','demand',.205,.11,19,'premise','msft','云厂商面向算力、数据中心和网络的资本投入强度。',true),
    node('trainingDemand','训练算力需求','TRAINING','demand',.205,.28,13,'model','model','大模型训练及后训练所需计算量的情景变量。',true),
    node('inferenceCost','单位推理成本','COST / TOKEN','demand',.205,.45,15,'model','model','每单位推理工作量的综合成本；下降可能通过需求弹性放大 Token 消耗。',true),
    node('tokenDemand','推理 Token 需求','TOKEN VOLUME','demand',.205,.62,17,'model','model','应用端实际推理调用量的情景指数。'),
    node('sovereignDemand','主权算力需求','SOVEREIGN AI','demand',.205,.79,12,'premise','model','政府及本地化算力项目需求。',true),
    node('dcBuildout','数据中心新建','DC BUILDOUT','demand',.205,.94,15,'model','model','可落地的数据中心机柜与设施建设量。'),
    node('generalGpu','通用 GPU 路线','GENERAL GPU','route',.355,.15,18,'premise','nvda','依靠通用加速器和软件生态交付训练及推理计算。'),
    node('customAsic','定制 ASIC 路线','CUSTOM ASIC','route',.355,.36,15,'premise','avgo','面向特定客户和负载优化的定制加速芯片路线。'),
    node('domesticCompute','本地替代算力','LOCAL SUBSTITUTE','route',.355,.57,14,'model','model','受地域、政策与生态约束影响的替代路线情景。'),
    node('opticalScale','光互连扩展','SCALE OUT','route',.355,.77,14,'premise','arista','集群规模增长对高速网络和光互连的需求。'),
    node('efficiency','软件效率提升','EFFICIENCY','route',.355,.94,12,'model','model','编译器、内核、量化和推理框架带来的单位算力效率提升。'),
    node('hbmSupply','HBM 有效供给','HBM CAPACITY','constraint',.505,.09,18,'premise','hynix','高带宽存储的有效可交付量，包含良率与封装配套。',true),
    node('cowosCapacity','CoWoS 先进封装','PACKAGING','constraint',.505,.24,17,'premise','tsmc','先进封装的有效产能及其利用率约束。',true),
    node('waferCapacity','先进制程晶圆','WAFER CAPACITY','constraint',.505,.39,14,'premise','tsmc','先进逻辑制程的可用晶圆产能。',true),
    node('networkCapacity','高速网络供给','NETWORK CAPACITY','constraint',.505,.54,13,'premise','arista','交换芯片、交换机与光互连的交付能力。',true),
    node('transformerCapacity','变压器 / 配电产能','POWER EQUIPMENT','constraint',.505,.69,14,'premise','eaton','输配电设备交付周期与有效产能。',true),
    node('coolingCapacity','液冷交付能力','THERMAL','constraint',.505,.84,13,'premise','vertiv','高密度机柜的散热与液冷系统交付能力。',true),
    node('constructionLabor','工程施工能力','LABOR','constraint',.505,.96,11,'model','model','数据中心工程设计、许可与施工资源约束。',true),
    node('accelerators','AI 加速卡','ACCELERATORS','chain',.665,.10,18,'premise','nvda','GPU 与 AI 加速卡系统的可交付收入池。'),
    node('memoryStack','HBM 存储价值','MEMORY STACK','chain',.665,.24,15,'premise','hynix','HBM 数量、价格与产品组合共同形成的价值池。'),
    node('foundryPackage','晶圆代工与封装','FOUNDRY / PKG','chain',.665,.38,15,'premise','tsmc','先进制程晶圆与先进封装服务价值池。'),
    node('networkFabric','网络与光互连','NETWORK FABRIC','chain',.665,.52,14,'premise','arista','数据中心以太网、交换与光互连价值池。'),
    node('powerCooling','电力与液冷系统','POWER / COOLING','chain',.665,.66,15,'premise','vertiv','配电、UPS、热管理与液冷基础设施价值池。'),
    node('cloudServices','云与算力服务','CLOUD SERVICES','chain',.665,.80,16,'premise','msft','云端训练、推理和 AI 平台的收入池。'),
    node('aiSoftware','AI 软件与应用','SOFTWARE','chain',.665,.94,13,'model','model','建立在算力与模型之上的应用及软件价值池。'),
    node('nvda','NVIDIA','NVDA','company',.845,.07,18,'fact','nvda','数据中心加速器、网络及软件平台暴露。'),
    node('amd','AMD','AMD','company',.845,.17,13,'fact','amd','数据中心 GPU 与 CPU 暴露。'),
    node('avgo','Broadcom','AVGO','company',.845,.27,14,'fact','avgo','定制加速器与网络芯片暴露。'),
    node('tsmc','TSMC','TSM','company',.845,.37,15,'fact','tsmc','先进制程与先进封装暴露。'),
    node('skhynix','SK hynix','000660.KS','company',.845,.47,15,'fact','hynix','HBM 与存储产品暴露。'),
    node('micron','Micron','MU','company',.845,.57,13,'fact','micron','HBM、DRAM 与 NAND 暴露。'),
    node('arista','Arista','ANET','company',.845,.67,13,'fact','arista','数据中心交换与网络暴露。'),
    node('vertiv','Vertiv','VRT','company',.845,.77,14,'fact','vertiv','数据中心电力与热管理暴露。'),
    node('eaton','Eaton','ETN','company',.845,.87,13,'fact','eaton','数据中心配电和电气设备暴露。'),
    node('msft','Microsoft','MSFT','company',.845,.97,16,'fact','msft','云服务及大规模 AI 基础设施资本开支暴露。')
  ];

  function edge(from, to, elasticity, lag, confidence, kind, note) {
    return { from, to, elasticity, lag, confidence, kind: kind || 'model', note: note || '模型弹性假设' };
  }
  const edges = [
    edge('rates','aiCapex',-.34,.82,.68,'model'), edge('itCycle','aiCapex',.38,.88,.62,'model'), edge('aiAdoption','tokenDemand',.55,.90,.66,'model'),
    edge('aiCapex','trainingDemand',.63,.92,.72,'premise'), edge('aiCapex','dcBuildout',.48,.80,.68,'premise'), edge('inferenceCost','tokenDemand',-.72,.92,.55,'model','Jevons 效应弹性'),
    edge('trainingDemand','generalGpu',.62,.92,.70,'premise'), edge('trainingDemand','customAsic',.28,.76,.55,'model'), edge('tokenDemand','generalGpu',.35,.86,.61,'model'), edge('tokenDemand','customAsic',.45,.90,.61,'model'),
    edge('tokenDemand','opticalScale',.46,.90,.64,'model'), edge('tokenDemand','dcBuildout',.28,.74,.56,'model'),
    edge('sovereignDemand','generalGpu',.26,.78,.51,'model'), edge('sovereignDemand','domesticCompute',.52,.88,.56,'model'), edge('exportControl','generalGpu',-.48,.90,.69,'model'), edge('exportControl','domesticCompute',.44,.78,.58,'model'),
    edge('efficiency','inferenceCost',-.58,.90,.62,'model'), edge('efficiency','tokenDemand',.24,.65,.48,'model'), edge('generalGpu','hbmSupply',-.34,.82,.66,'premise','需求增长压低有效供给余量'), edge('generalGpu','cowosCapacity',-.46,.90,.71,'premise','需求增长压低有效供给余量'),
    edge('generalGpu','waferCapacity',-.31,.83,.69,'premise','需求增长压低有效供给余量'), edge('customAsic','waferCapacity',-.26,.82,.65,'premise'), edge('customAsic','cowosCapacity',-.24,.78,.61,'premise'), edge('opticalScale','networkCapacity',-.59,.91,.72,'premise'),
    edge('dcBuildout','transformerCapacity',-.55,.90,.71,'premise'), edge('dcBuildout','coolingCapacity',-.47,.88,.71,'premise'), edge('dcBuildout','constructionLabor',-.36,.80,.55,'model'), edge('powerSupply','dcBuildout',.62,.92,.72,'premise'),
    edge('hbmSupply','accelerators',.31,.86,.62,'model'), edge('cowosCapacity','accelerators',.39,.92,.69,'model'), edge('waferCapacity','accelerators',.28,.88,.68,'model'), edge('generalGpu','accelerators',.64,.93,.72,'model'),
    edge('hbmSupply','memoryStack',.66,.94,.66,'model'), edge('generalGpu','memoryStack',.28,.78,.63,'model'), edge('cowosCapacity','foundryPackage',.54,.92,.70,'model'), edge('waferCapacity','foundryPackage',.49,.92,.70,'model'),
    edge('networkCapacity','networkFabric',.58,.92,.68,'model'), edge('opticalScale','networkFabric',.43,.89,.67,'model'), edge('transformerCapacity','powerCooling',.35,.80,.61,'model'), edge('coolingCapacity','powerCooling',.47,.90,.67,'model'),
    edge('dcBuildout','powerCooling',.55,.92,.69,'model'), edge('tokenDemand','cloudServices',.41,.86,.61,'model'), edge('aiCapex','cloudServices',.18,.62,.54,'model'), edge('aiAdoption','aiSoftware',.52,.91,.60,'model'),
    edge('cloudServices','aiSoftware',.28,.70,.54,'model'), edge('accelerators','nvda',.72,.95,.75,'model'), edge('accelerators','amd',.49,.90,.63,'model'), edge('accelerators','avgo',.16,.68,.49,'model'),
    edge('memoryStack','skhynix',.70,.95,.73,'model'), edge('memoryStack','micron',.55,.92,.69,'model'), edge('foundryPackage','tsmc',.69,.96,.76,'model'), edge('networkFabric','arista',.66,.95,.73,'model'),
    edge('networkFabric','avgo',.36,.84,.64,'model'), edge('powerCooling','vertiv',.68,.95,.74,'model'), edge('powerCooling','eaton',.48,.90,.70,'model'), edge('cloudServices','msft',.47,.91,.69,'model')
  ];

  const companies = [
    { id:'nvda', ticker:'NVDA', name:'NVIDIA', sourceId:'nvda', exposures:{accelerators:.82,networkFabric:.12}, revenueSensitivity:.58, marginSensitivity:.18, capexSensitivity:.04, multiple:34, duration:1.25 },
    { id:'amd', ticker:'AMD', name:'AMD', sourceId:'amd', exposures:{accelerators:.67}, revenueSensitivity:.52, marginSensitivity:.16, capexSensitivity:.05, multiple:31, duration:1.18 },
    { id:'avgo', ticker:'AVGO', name:'Broadcom', sourceId:'avgo', exposures:{networkFabric:.46,accelerators:.25}, revenueSensitivity:.42, marginSensitivity:.12, capexSensitivity:.03, multiple:29, duration:1.05 },
    { id:'tsmc', ticker:'TSM', name:'TSMC', sourceId:'tsmc', exposures:{foundryPackage:.76,accelerators:.12}, revenueSensitivity:.36, marginSensitivity:.10, capexSensitivity:.18, multiple:21, duration:.82 },
    { id:'skhynix', ticker:'000660', name:'SK hynix', sourceId:'hynix', exposures:{memoryStack:.83}, revenueSensitivity:.51, marginSensitivity:.30, capexSensitivity:.16, supplyPricePenalty:.20, multiple:9, duration:.58 },
    { id:'micron', ticker:'MU', name:'Micron', sourceId:'micron', exposures:{memoryStack:.66}, revenueSensitivity:.49, marginSensitivity:.27, capexSensitivity:.14, supplyPricePenalty:.18, multiple:11, duration:.62 },
    { id:'arista', ticker:'ANET', name:'Arista', sourceId:'arista', exposures:{networkFabric:.79}, revenueSensitivity:.45, marginSensitivity:.10, capexSensitivity:.03, multiple:38, duration:1.20 },
    { id:'vertiv', ticker:'VRT', name:'Vertiv', sourceId:'vertiv', exposures:{powerCooling:.82,dcBuildout:.18}, revenueSensitivity:.46, marginSensitivity:.12, capexSensitivity:.04, multiple:31, duration:1.12 },
    { id:'eaton', ticker:'ETN', name:'Eaton', sourceId:'eaton', exposures:{powerCooling:.57,transformerCapacity:.18}, revenueSensitivity:.29, marginSensitivity:.08, capexSensitivity:.03, multiple:28, duration:.96 },
    { id:'msft', ticker:'MSFT', name:'Microsoft', sourceId:'msft', exposures:{cloudServices:.62,aiSoftware:.22}, revenueSensitivity:.26, marginSensitivity:.06, capexSensitivity:.32, multiple:30, duration:1.16 }
  ];

  const interactions = [
    { a:'aiCapex', b:'hbmSupply', target:'memoryStack', coefficient:.0028, label:'需求与供给共同决定 HBM 定价权' },
    { a:'exportControl', b:'domesticCompute', target:'accelerators', coefficient:.0020, label:'管制与替代路线形成区域分化' },
    { a:'inferenceCost', b:'aiAdoption', target:'tokenDemand', coefficient:-.0024, label:'成本下降与应用渗透共同放大 Token 需求' },
    { a:'powerSupply', b:'dcBuildout', target:'powerCooling', coefficient:.0021, label:'电力约束改变基础设施价值量' }
  ];

  const scenarioDefinitions = [
    { id:'aiCapex', patterns:['资本开支','capex','云厂商投入'], label:'AI 资本开支' },
    { id:'hbmSupply', patterns:['hbm','高带宽存储','高宽存'], label:'HBM 有效供给' },
    { id:'inferenceCost', patterns:['推理单位成本','推理成本','单位推理','token 成本','token成本'], label:'单位推理成本' },
    { id:'exportControl', patterns:['出口管制','出口限制','禁运'], label:'出口管制强度' },
    { id:'cowosCapacity', patterns:['cowos','先进封装','封装产能'], label:'CoWoS 先进封装' },
    { id:'powerSupply', patterns:['电力供给','可用电力','供电'], label:'可用电力供给' },
    { id:'rates', patterns:['实际利率','利率','资本成本','折现率'], label:'实际利率' },
    { id:'aiAdoption', patterns:['ai 渗透','应用渗透','ai应用'], label:'AI 应用渗透' },
    { id:'networkCapacity', patterns:['网络供给','交换机供给','光互连供给'], label:'高速网络供给' }
  ];
  window.SANDBOX_DATA = { sources, sourceNames, layerNames, nodes, edges, companies, interactions, scenarioDefinitions };
}());
