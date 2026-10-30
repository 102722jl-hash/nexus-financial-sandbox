const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

let checks=0;
function check(value,message){assert.ok(value,message);checks+=1;}
function equal(actual,expected,message){assert.equal(actual,expected,message);checks+=1;}
function source(file){return fs.readFileSync(path.resolve(__dirname,file),'utf8');}
function load(context,file){vm.runInContext(source(file),context,{filename:file});}

function loadDomain(domainId){
  const context={console,structuredClone,URLSearchParams};
  context.window=context;
  vm.createContext(context);
  const files=domainId==='coal-steel'?
    ['coal-data.js','coal-db-snapshot.js','coal-semantics.js','legacy-engine.js','coal-model-config.js','coal-engine.js','data-contract.js','domain-coal-steel.js','coal-company-adapter.js','domain-coal-package.js']:
    ['legacy-data.js','v26-semantics.js','legacy-engine.js','v2-model-config.js','v2-engine.js','data-contract.js','domain-ai-infra.js','db-coverage-snapshot.js','company-adapter.js','domain-ai-package.js'];
  files.forEach((file)=>load(context,file));
  load(context,'v216-domain-resolver.js');
  load(context,'graph-compiler.js');
  context.NEXUS_REQUESTED_DOMAIN=domainId;
  load(context,'active-domain.js');
  load(context,'market-valuation-data.js');
  load(context,'market-valuation-engine.js');
  load(context,'run-manifest.js');
  return context;
}

const ai=loadDomain('ai-infrastructure');
const coal=loadDomain('coal-steel');
const aiPackage=ai.NEXUS_ACTIVE_PACKAGE;
const coalPackage=coal.NEXUS_ACTIVE_PACKAGE;

equal(ai.NEXUS_ACTIVE_RUNTIME.id,'ai-infrastructure','AI 运行时必须登记正确领域');
equal(coal.NEXUS_ACTIVE_RUNTIME.id,'coal-steel','煤钢运行时必须登记正确领域');
equal(aiPackage.id,'ai-infrastructure');
equal(coalPackage.id,'coal-steel');
equal(aiPackage.nodes.length,40,'AI 领域节点数应保持冻结基线');
equal(coalPackage.nodes.length,27,'煤钢领域必须加载独立节点集合');
equal(coalPackage.edges.length,33,'煤钢领域必须加载独立边集合');
equal(aiPackage.companies.length,10,'AI 领域必须保留十家公司');
equal(coalPackage.companies.length,5,'煤钢领域必须加载五家公司');

const aiNodeIds=new Set(aiPackage.nodes.map((item)=>item.id));
const coalNodeIds=new Set(coalPackage.nodes.map((item)=>item.id));
check(aiNodeIds.has('aiCapex')&&aiNodeIds.has('hbmSupply')&&aiNodeIds.has('nvda'),'AI 包必须包含自己的情景、约束与公司节点');
check(!aiNodeIds.has('cokingCoalPrice')&&!aiNodeIds.has('shenhua'),'AI 包不得泄漏煤钢节点');
check(coalNodeIds.has('cokingCoalPrice')&&coalNodeIds.has('steelRawCost')&&coalNodeIds.has('shenhua'),'煤钢包必须包含自己的价格、成本与公司节点');
check(!coalNodeIds.has('aiCapex')&&!coalNodeIds.has('hbmSupply')&&!coalNodeIds.has('nvda'),'煤钢包不得泄漏 AI 节点');
const sharedNodeIds=[...aiNodeIds].filter((id)=>coalNodeIds.has(id));
check(sharedNodeIds.length===1&&sharedNodeIds[0]==='rates','只有定义一致的实际利率变量允许跨领域复用');

equal(ai.NEXUS_V29_GRAPH_COMPILER.validateDomain(aiPackage).valid,true);
equal(coal.NEXUS_V29_GRAPH_COMPILER.validateDomain(coalPackage).valid,true);
const aiCompanies=['nvda','tsmc','skhynix','vertiv','msft'];
const coalCompanies=['shenhua','shaanxi','yankuang','baosteel','citicsteel'];
const aiGraphs=aiCompanies.map((id)=>ai.NEXUS_V29_GRAPH_COMPILER.compile(aiPackage,id,['exportControl']));
const coalGraphs=coalCompanies.map((id)=>coal.NEXUS_V29_GRAPH_COMPILER.compile(coalPackage,id,['cokingCoalPrice']));
check(aiGraphs.every((item)=>item.status==='RESOLVED'&&item.domainId==='ai-infrastructure'),'AI 五家核心公司必须解析到 AI 包');
check(coalGraphs.every((item)=>item.status==='RESOLVED'&&item.domainId==='coal-steel'),'煤钢五家公司必须解析到煤钢包');
equal(new Set(aiGraphs.map((item)=>item.graphHash)).size,5,'AI 公司切换必须产生不同依赖图');
equal(new Set(coalGraphs.map((item)=>item.graphHash)).size,5,'煤钢公司切换必须产生不同依赖图');
equal(ai.NEXUS_V29_GRAPH_COMPILER.compile(aiPackage,'shenhua',['exportControl']).status,'ABSTAIN','AI 包不得接入煤钢公司');
equal(coal.NEXUS_V29_GRAPH_COMPILER.compile(coalPackage,'nvda',['cokingCoalPrice']).status,'ABSTAIN','煤钢包不得接入 AI 公司');

const aiResult=ai.SANDBOX_V2_ENGINE.evaluate(ai.NEXUS_ACTIVE_RUNTIME.defaults.A.shocks,12).base;
const coalResult=coal.SANDBOX_V2_ENGINE.evaluate(coal.NEXUS_ACTIVE_RUNTIME.defaults.A.shocks,12).base;
equal(aiResult.companies.length,10,'AI 引擎必须计算 AI 公司集合');
equal(coalResult.companies.length,5,'煤钢引擎必须计算煤钢公司集合');
check(aiResult.companies.some((item)=>item.id==='nvda')&&!aiResult.companies.some((item)=>item.id==='shenhua'),'AI 结果不得混入煤钢公司');
check(coalResult.companies.some((item)=>item.id==='shenhua')&&!coalResult.companies.some((item)=>item.id==='nvda'),'煤钢结果不得混入 AI 公司');
check(ai.SANDBOX_ENGINE.parseScenario('HBM 供给增加 50%').shocks.some((item)=>item.id==='hbmSupply'),'AI 自然语言情景必须映射到 AI 节点');
check(coal.SANDBOX_ENGINE.parseScenario('焦煤价格下降 20%').shocks.some((item)=>item.id==='cokingCoalPrice'),'煤钢自然语言情景必须映射到煤钢节点');
const coalRejected=coal.SANDBOX_ENGINE.parseScenario('HBM 供给增加 50%');
check(Boolean(coalRejected.error)&&coalRejected.shocks.length===0,'煤钢情景解析器不得回退到 AI 节点');
check(coalRejected.error.includes('焦煤价格')&&!coalRejected.error.includes('HBM'),'煤钢解析失败提示必须使用当前领域词典');

const aiContract=ai.NEXUS_V25_RUN.contractCheck();
const coalContract=coal.NEXUS_V25_RUN.contractCheck();
equal(aiContract.nodes.length,aiPackage.nodes.length);
equal(coalContract.nodes.length,coalPackage.nodes.length);
check(aiContract.evidence.filter((item)=>item.sourceTier!=='MODEL').every((item)=>item.reviewStatus==='NEEDS_HUMAN_REVIEW'),'AI 未定位证据必须保留人工审核');
check(coalContract.evidence.filter((item)=>item.sourceTier!=='MODEL').every((item)=>item.reviewStatus==='NEEDS_HUMAN_REVIEW'),'煤钢数据库候选不得提升为来源事实');
check(coal.SANDBOX_DATA.nodes.filter((item)=>item.layer==='company').every((item)=>item.sourceId==='postgres'&&item.sourceType==='premise'),'煤钢公司节点必须映射 PostgreSQL 候选底座');
check(coal.SANDBOX_DATA.nodes.filter((item)=>item.layer==='company').every((item)=>item.valueClass==='CALCULATED_RESULT'),'公司节点必须表达计算结果而不是已披露事实');

equal(ai.NEXUS_V25_RUN.version,'2.16.0');
equal(coal.NEXUS_V25_RUN.version,'2.16.0');
equal(ai.NEXUS_V25_RUN.parentVersion,'2.15.3-frozen');
equal(coal.NEXUS_V25_RUN.parentVersion,'2.15.3-frozen');
equal(ai.NEXUS_V25_RUN.domainPackage,aiPackage.version);
equal(coal.NEXUS_V25_RUN.domainPackage,coalPackage.version);
equal(ai.NEXUS_V25_RUN.formal_ready,false);
equal(coal.NEXUS_V25_RUN.formal_ready,false);
equal(ai.NEXUS_V25_RUN.causalConclusion,'ABSTAIN');
equal(coal.NEXUS_V25_RUN.causalConclusion,'ABSTAIN');
equal(ai.NEXUS_V25_RUN.status,'NEEDS_HUMAN_REVIEW');
equal(coal.NEXUS_V25_RUN.status,'NEEDS_HUMAN_REVIEW');
equal(ai.NEXUS_ACTIVE_RUNTIME.database.targetCoverage.status,'DATA_MISSING');
equal(coal.NEXUS_ACTIVE_RUNTIME.database.audit.formal_ready,false);
equal(coal.NEXUS_ACTIVE_RUNTIME.database.audit.causalConclusion,'ABSTAIN');

equal(ai.NEXUS_V214_MARKET_VALUATION.schemaVersion,'market-calibrated-scenario-valuation-1.0.0');
equal(coal.NEXUS_V214_MARKET_VALUATION.schemaVersion,'market-calibrated-scenario-valuation-1.0.0');
equal(ai.NEXUS_V25_RUN.valuationEngine,ai.NEXUS_V214_MARKET_VALUATION.schemaVersion);
equal(coal.NEXUS_V25_RUN.marketDataVersion,coal.NEXUS_V214_MARKET_DATA.schemaVersion);
const aiValuations=aiResult.companies.map((company)=>ai.NEXUS_V214_MARKET_VALUATION.evaluate(company));
const coalValuations=coalResult.companies.map((company)=>coal.NEXUS_V214_MARKET_VALUATION.evaluate(company));
check(aiValuations.every((item)=>item.status==='CANDIDATE_VALUATION'),'AI 十家公司必须生成候选情景估值');
check(coalValuations.every((item)=>item.status==='CANDIDATE_VALUATION'),'煤钢五家公司必须生成候选情景估值');
check([...aiValuations,...coalValuations].every((item)=>Number.isFinite(item.currentMarketCap)&&Number.isFinite(item.baselineEquityValue)&&Number.isFinite(item.scenarioEquityValue)&&Number.isFinite(item.valueChangeAmount)&&Number.isFinite(item.valueChangePct)),'所有公司必须输出当前、基准、情景价值及变化金额比例');
check(aiValuations.every((item)=>item.method==='MARKET_CALIBRATED_EV_EBITDA'),'AI 公司必须使用市场校准 EV/EBITDA');
check(coalValuations.every((item)=>item.method==='MARKET_CALIBRATED_PE'),'煤钢公司必须使用市场校准 P/E');
check([...aiValuations,...coalValuations].every((item)=>Math.abs(item.baselineEquityValue-item.currentMarketCap)<.001),'市场校准基准价值必须回加到当前市值');
const attributionDiffs=[...aiValuations,...coalValuations].map((item)=>({id:item.companyId,diff:item.attribution.operations+item.attribution.multiple+item.attribution.cashFlow-item.valueChangeAmount}));
check(attributionDiffs.every((item)=>Math.abs(item.diff)<.01),'经营、倍数与现金流归因必须回加到市值变化金额');
check([...aiValuations,...coalValuations].every((item)=>item.formal_ready===false&&item.reviewStatus==='NEEDS_HUMAN_REVIEW'),'候选估值不得提升为正式研究结果');
equal(ai.NEXUS_V214_MARKET_VALUATION.profile('nvda').currentMarketCap,undefined);
equal(ai.NEXUS_V214_MARKET_VALUATION.profile('nvda').marketCapBn,5347.51238);
equal(coal.NEXUS_V214_MARKET_VALUATION.profile('shenhua').marketCapBn,1058.010605154);
equal(coal.NEXUS_V214_MARKET_VALUATION.profile('shenhua').quoteDate,'2026-08-31');
check(coal.NEXUS_ACTIVE_RUNTIME.database.companies.shenhua.valuationLineage.cutoff==='2026-05-08','煤钢财务底座必须保留截止时间');
check(ai.NEXUS_V214_MARKET_DATA.audit.formal_ready===false&&ai.NEXUS_V214_MARKET_DATA.audit.limitations.length>=3,'市场数据包必须显示逐项审核缺口');
const aiRanking=ai.NEXUS_V214_MARKET_VALUATION.evaluateAll(aiResult.companies);
check(aiRanking.every((item,index)=>index===0||aiRanking[index-1].valueChangePct>=item.valueChangePct),'公司排名必须按情景市值变化比例排序');
check(new Set(aiRanking.map((item)=>item.valueChangePct)).size>3,'市值排名必须来自公司专属估值而不是统一占位值');

const html=source('index.html');
const loader=source('domain-loader.js');
const app=source('app.js');
const domainUi=source('v212-domain-ui.js');
const drawer=source('v210-financial-drawer.js');
const manifest=source('run-manifest.js');
const valuationUi=source('v214-market-value-ui.js');
const resolver=source('v216-domain-resolver.js');
const overlay=source('v216-runtime-overlay.js');
check(html.includes('NEXUS V2.19')&&html.includes('id="domainSelect"'),'页面必须标识当前版本并提供领域选择器');
check(html.includes('value="ai-infrastructure"')&&html.includes('value="coal-steel"'),'领域选择器必须提供 AI 与煤钢');
check(html.includes('domain-loader.js?v=2.17.0')&&html.indexOf('domain-loader.js')<html.indexOf('graph-compiler.js'),'领域资源必须先于共享引擎适配层加载');
check(html.indexOf('v216-domain-resolver.js')<html.indexOf('v216-runtime-overlay.js')&&html.indexOf('v216-runtime-overlay.js')<html.indexOf('active-domain.js'),'领域解析和运行叠加必须在活动领域运行清单之前加载');
check(html.indexOf('active-domain.js')<html.indexOf('market-valuation-data.js')&&html.indexOf('market-valuation-data.js')<html.indexOf('market-valuation-engine.js')&&html.indexOf('market-valuation-engine.js')<html.indexOf('run-manifest.js'),'市场数据与估值引擎必须在运行清单前加载');
check(loader.includes("requested==='coal-steel'?'coal-steel':'ai-infrastructure'"),'未知领域必须安全回到 AI 基线');
check(loader.includes("'coal-data.js'")&&loader.includes("'legacy-data.js'")&&loader.includes("'legacy-engine.js'"),'领域加载器必须选择互斥且本地冻结的数据入口');
check(!loader.includes('../financial-world-sandbox/'),'当前版本不得依赖服务根目录之外的冻结基础脚本');
check(fs.existsSync('legacy-data.js')&&fs.existsSync('legacy-engine.js'),'冻结基础数据与计算引擎必须随当前版本部署');
check(loader.includes("'coal-engine.js'")&&loader.includes("'v2-engine.js'"),'领域加载器必须选择互斥的计算引擎');
check(app.includes('runtime.defaults')&&app.includes('runtime.selectedCompany')&&app.includes('runtime.selectedNode'),'共享页面必须从活动领域读取默认状态');
check(app.includes("'data','governance'")&&app.includes("get('view')")&&app.includes("switchView(state.view)"),'六个研究视图必须支持 URL 直接预览验收');
check(app.includes("'nexus-v2.17-'+runtime.id+'-versions'")&&app.includes("domainId:runtime.id"),'保存与导出必须按领域隔离');
check(domainUi.includes("url.searchParams.set('domain',next)")&&domainUi.includes('window.location.assign'),'切换领域必须重新加载完整资源图');
check(domainUi.includes("document.title='NEXUS V2.19")&&domainUi.includes("set('v','2.19.11')"),'页面标题与领域切换缓存版本必须使用当前资源版本');
check(domainUi.includes("[data-focus=\"upstream\"],[data-focus=\"capacity\"],[data-focus=\"infrastructure\"]"),'煤钢页必须隐藏 AI 专属研究视角');
check(drawer.includes('runtime.financialBridge.fcfFormula'),'财务抽屉必须使用活动领域公式');
check(source('active-domain.js').includes('× 0.32')&&source('active-domain.js').includes('× 0.48'),'煤钢与 AI 必须保留不同 FCF 桥接参数');
check(manifest.includes("runId:'v216-'+runtime.id")&&manifest.includes("parentVersion:'2.15.3-frozen'")&&manifest.includes("domainResolver:window.NEXUS_V216_DOMAIN_RESOLVER.schemaVersion")&&manifest.includes("valuationEngine:window.NEXUS_V214_MARKET_VALUATION.schemaVersion"),'运行清单必须记录冻结父版本、领域解析器和估值引擎版本');
check(manifest.includes("dataCutoff:coal?'2026-08-31':'2026-09-01'"),'数据截止时间必须使用可比较的 ISO 日期');
const valuationIds=['v213CurrentMarketCap','v213BaselineValue','v213ScenarioValue','v213ValueChange','v213MarketUpside','v213Missing'];
check(valuationIds.every((id)=>html.includes('id="'+id+'"')),'公司页必须显示五项估值结果和缺口账');
check(['当前市值','基准情景股权价值','冲击后股权价值','情景价值变化','相对当前市值空间'].every((label)=>html.includes(label)),'估值账必须使用真实价值口径');
check(valuationUi.includes('CANDIDATE_VALUATION')&&valuationUi.includes('valueChangeAmount')&&valuationUi.includes('valueChangePct'),'估值 UI 必须显示候选状态、市值变化金额和比例');
check(app.includes('companyValuationResults')&&app.includes('valuationContractVersion'),'导出结果必须带公司估值门禁结果和契约版本');
const visibleSources=[html,app,drawer,source('v24-enhancements.js'),source('active-domain.js'),source('v27-playback.js')].join('\n');
check(!visibleSources.includes('估值贡献'),'当前版本可见文案不得继续使用旧估值贡献表述');
check(!visibleSources.includes('价值压力'),'当前版本必须删除价值压力这一产品概念');
const workbench=source('v216-workbench.js'),server=source('server.py');
for(const id of ['v215ProfilePostgres','v215SourceFile','v215MappingTable','v215BuildPackage','v215AiProvider','v215TaskQueue','v215Quarantine','v215ValuationMode'])check(html.includes('id="'+id+'"'),'V1.0/V1.1工作台缺少 '+id);
for(const id of ['v216ImportIntent','v216DetectedDomain','v216ScoreList','v216DiffSummary','v216ApprovePlan','v216ActivatePackage'])check(html.includes('id="'+id+'"'),'V2.16领域编译工作台缺少 '+id);
check(workbench.includes('MARKET_CALIBRATED_SCENARIO')&&workbench.includes('HUMAN_CONFIRMED')&&workbench.includes('api.buildPackage')&&workbench.includes('nexus-v2.17-active-import'),'工作台必须实现估值模式、双重人工确认、数据包构建和激活');
check(workbench.includes("get('demo')")&&workbench.includes("['ai','coal','ev']"),'领域解析器必须提供三个只读演示入口用于验收');
check(server.includes('default_transaction_read_only=on')&&server.includes('SET TRANSACTION READ ONLY')&&server.includes('/api/packages/build')&&server.includes('DOMAIN_PLAN_REVIEW_REQUIRED'),'本地连接器必须强制只读并执行领域计划门禁');
check(server.includes('default=4180'),'当前版本本地服务必须使用独立端口 4180');
check(server.includes('data_snapshot.json')&&server.includes('company_adapters.json')&&server.includes('network_diff.json')&&server.includes('activation.json'),'候选包必须保存快照、公司适配、网络差异和激活清单');
check(overlay.includes("status!=='ACTIVATED'")&&overlay.includes("row.scope==='DOMAIN_NODE'")&&overlay.includes("formalReady:false"),'运行叠加只能加载已激活的领域节点候选，且不得提升为正式事实');
check(resolver.includes("'new-energy-vehicle'")&&resolver.includes("status:'CANDIDATE_ONLY'")&&resolver.includes("action='CREATE_DOMAIN_CANDIDATE'"),'新能源汽车必须作为隔离候选领域而不是复用 AI 或焦煤节点');
check(app.includes('情景市值变化')&&drawer.includes('情景市值变化'),'公司节点、排名和财务抽屉必须使用市值变化口径');
check(!/(INSERT|UPDATE|DELETE|ALTER|DROP|CREATE|GRANT|REVOKE|TRUNCATE)/.test(source('readonly_financial_query.py')),'数据库查询适配器不得包含写入或权限语句');

const domainResolver=ai.NEXUS_V216_DOMAIN_RESOLVER;
const aiImport=domainResolver.compile({activeDomain:'ai-infrastructure',intent:'supplement',fileName:'ai-supply.csv',entityHints:['NVDA'],profile:[{column:'ai_capex',candidateValue:-30},{column:'hbm_supply',candidateValue:50},{column:'cowos_capacity',candidateValue:40}]});
equal(aiImport.detectedDomain,'ai-infrastructure','AI 字段必须解析到 AI 领域');
equal(aiImport.action,'UPDATE_ACTIVE_DOMAIN','同领域导入必须更新当前领域而不是重建其他行业');
check(aiImport.diff.updatedNodes.includes('aiCapex')&&aiImport.diff.updatedNodes.includes('hbmSupply'),'AI 导入必须更新匹配节点');
equal(aiImport.diff.addedNodes.length,0,'同领域补充不得新增整套行业节点');
equal(aiImport.diff.unavailableNodes.length,0,'补充快照不得把未提供节点错误降为不可用');
const metadataImport=domainResolver.compile({activeDomain:'ai-infrastructure',intent:'supplement',fileName:'ai.csv',profile:[{column:'report_date'},{column:'ticker'},{column:'hbm_supply'}]});
check(metadataImport.mappings.some((item)=>item.target==='observationDate'&&item.scope==='SOURCE_METADATA'),'日期必须归类为来源元数据');
check(metadataImport.mappings.some((item)=>item.target==='entityCode'&&item.scope==='SOURCE_METADATA'),'证券代码必须归类为来源元数据');
equal(metadataImport.unknownFields.length,0,'标准日期和证券代码不得显示为行业外字段');

const coalImport=domainResolver.compile({activeDomain:'ai-infrastructure',intent:'supplement',fileName:'coal-steel.csv',entityHints:['601088.SH'],profile:[{column:'coking_coal_price',candidateValue:-20},{column:'steel_demand',candidateValue:-15},{column:'port_inventory',candidateValue:8.2}]});
equal(coalImport.detectedDomain,'coal-steel','焦煤字段必须解析到煤钢领域');
equal(coalImport.action,'SWITCH_DOMAIN','跨领域导入必须切换完整领域包');
check(coalImport.activation.allowed&&coalImport.diff.sharedNodes.length===1&&coalImport.diff.sharedNodes[0]==='rates','AI 与煤钢只允许共享语义一致的实际利率节点');
check(coalImport.diff.addedNodes.includes('cokingCoalPrice')&&coalImport.diff.removedNodes.includes('hbmSupply'),'跨领域差异必须显示新增焦煤节点和移除 AI 节点');

const evImport=domainResolver.compile({activeDomain:'ai-infrastructure',intent:'new-domain',fileName:'ev-battery.csv',entityHints:['300750.SZ'],profile:[{column:'lithium_price',candidateValue:-30},{column:'battery_capacity',candidateValue:18},{column:'ev_demand',candidateValue:12}]});
equal(evImport.detectedDomain,'new-energy-vehicle','锂电字段必须解析到新能源汽车候选领域');
equal(evImport.action,'CREATE_DOMAIN_CANDIDATE','未实现行业只能生成候选领域');
equal(evImport.activation.allowed,false,'候选领域不得进入确定性运行');

const genericImport=domainResolver.compile({activeDomain:'ai-infrastructure',intent:'supplement',fileName:'financials.csv',profile:[{column:'revenue'},{column:'net_profit'}]});
equal(genericImport.detectedDomain,null,'通用财务字段不足以推断行业');
equal(genericImport.action,'HOLD_FOR_REVIEW','行业无法识别时必须等待人工选择');

const candidateCompany=domainResolver.compile({activeDomain:'ai-infrastructure',intent:'supplement',companyHint:'Example Compute Ltd',fileName:'ai-company.csv',profile:[{column:'hbm_supply'}]});
equal(candidateCompany.action,'ADD_COMPANY_CANDIDATE','未知公司只能形成公司候选');
equal(candidateCompany.activation.allowed,false,'缺少公司适配器时不得激活精确模型');
equal(candidateCompany.companies.candidate.status,'EXPOSURE_ONLY','未知公司必须降级为 EXPOSURE_ONLY');

const replacement=domainResolver.compile({activeDomain:'coal-steel',intent:'replace',fileName:'coal.csv',profile:[{column:'coking_coal_price'}]});
check(replacement.diff.unavailableNodes.length>0,'完整替换模式必须明确显示未提供节点');
check(!replacement.diff.unavailableNodes.includes('shenhua'),'替换快照不得把未上传的公司实体当作零值删除');

console.log('Financial sandbox V2.16 domain compiler tests: '+checks+'/'+checks+' passed');
