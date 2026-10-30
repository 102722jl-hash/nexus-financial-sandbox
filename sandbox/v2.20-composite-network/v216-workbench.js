(function(){
  const bridge=window.NEXUS_V24_BRIDGE;
  const valuation=window.NEXUS_V214_MARKET_VALUATION;
  const runtime=window.NEXUS_ACTIVE_RUNTIME;
  const pkg=window.NEXUS_ACTIVE_PACKAGE;
  const resolver=window.NEXUS_V216_DOMAIN_RESOLVER;
  const api=window.NEXUS_API_CLIENT;
  const el=(id)=>document.getElementById(id);
  if(!bridge||!valuation||!resolver)return;

  const state={connector:null,profile:null,profileRows:[],entityHints:[],sourceMeta:null,mappings:[],mappingApproved:false,plan:null,planApproved:false,packageBuild:null,tasks:[],quarantine:[],rankMode:'changePct',intent:'supplement',companyHint:''};
  const esc=(value)=>String(value??'').replace(/[&<>"']/g,(char)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const pct=(value)=>value==null?'DATA_MISSING':(value>=0?'+':'')+Number(value).toFixed(1)+'%';
  const money=(value,result)=>{if(value==null)return'DATA_MISSING';if(result.currency==='USD')return'$'+Number(value).toLocaleString('zh-CN',{maximumFractionDigits:1})+'bn';if(result.currency==='CNY')return'¥'+Number(value).toLocaleString('zh-CN',{maximumFractionDigits:1})+'bn';if(result.currency==='KRW')return'₩'+Number(value/1000).toLocaleString('zh-CN',{maximumFractionDigits:1})+'tn';return result.currency+' '+value;};
  const currentCompany=()=>bridge.current()?.base.companies.find((item)=>item.id===bridge.state.selectedCompany)||bridge.current()?.base.companies[0];
  const currentValuation=()=>valuation.evaluate(currentCompany());
  const className=(value)=>String(value||'').toLowerCase().replace(/[^a-z0-9_-]/g,'-');

  function resolverInput(){return{activeDomain:runtime.id,intent:state.intent,companyHint:state.companyHint,fileName:state.sourceMeta?.fileName||'',profile:state.profileRows,entityHints:state.entityHints};}
  function analyze(){
    state.plan=resolver.compile(resolverInput());
    state.mappings=state.plan.mappings;
    state.mappingApproved=false;
    state.planApproved=false;
    state.packageBuild=null;
    state.quarantine=state.profile?.cutoff_status==='QUARANTINED_AFTER_CUTOFF'?[{code:'DATA_AFTER_CUTOFF',reason:'导入数据包含研究截止时间之后的记录'}]:[];
    render();
  }
  function renderProfile(){
    const rows=state.profile?Object.entries(state.profile):[['运行模式','STATIC PACKAGE'],['领域包',pkg.version],['数据截止',window.NEXUS_V25_RUN.dataCutoff],['数据库快照',window.NEXUS_V25_RUN.databaseSnapshot],['活动导入',window.NEXUS_V216_RUNTIME_IMPORT?.status||'NONE'],['原始凭据','NOT EXPORTED']];
    el('v215SourceProfile').innerHTML=rows.map(([key,value])=>'<div><span>'+esc(key)+'</span><b>'+esc(value)+'</b></div>').join('');
    el('v215ConnectorState').textContent=state.connector||'STATIC MODE';
  }
  function renderMappings(){
    el('v215MappingState').textContent=state.mappingApproved?'HUMAN_CONFIRMED':state.mappings.length?'WAITING_REVIEW':'WAITING_SOURCE';
    el('v215MappingTable').innerHTML=state.mappings.length?state.mappings.map((row)=>'<div><span>'+esc(row.source)+'</span><b>'+esc(row.target)+'<small>'+esc(row.label)+' · '+esc(row.scope)+'</small></b><i class="'+className(row.status)+'">'+esc(row.status)+'</i></div>').join(''):'<p class="v216-empty">尚无导入字段。</p>';
    el('v215ApproveMappings').disabled=!state.mappings.some((row)=>row.status==='MATCHED');
  }
  function scoreWidth(score,max){return Math.max(2,Math.round(score/Math.max(1,max)*100));}
  function listBlock(label,items,kind){return'<div class="'+kind+'"><span>'+label+'</span><b>'+items.length+'</b><small>'+esc(items.slice(0,8).join(' · ')||'NONE')+(items.length>8?' · …':'')+'</small></div>';}
  function renderResolution(){
    const plan=state.plan;
    el('v216ImportIntent').value=state.intent;
    el('v216CompanyHint').value=state.companyHint;
    if(!plan){
      el('v216DomainState').textContent='WAITING_SOURCE';
      el('v216DetectedDomain').textContent='尚未识别';
      el('v216Action').textContent='HOLD_FOR_REVIEW';
      el('v216ScoreList').innerHTML='<p class="v216-empty">导入数据后生成领域候选。</p>';
      el('v216DiffSummary').innerHTML='';
      el('v216DiffLists').innerHTML='';
      el('v216GateList').innerHTML='';
      el('v216ApprovePlan').disabled=true;
      return;
    }
    const target=plan.detectedDomain?resolver.catalogs[plan.detectedDomain]:null,max=Math.max(...plan.scores.map((item)=>item.score),1);
    el('v216DomainState').textContent=plan.gates.domain;
    el('v216DetectedDomain').textContent=target?target.name:'未识别';
    el('v216Action').textContent=plan.action;
    el('v216ScoreList').innerHTML=plan.scores.map((item)=>'<div><span>'+esc(item.name)+'</span><i><b style="width:'+scoreWidth(item.score,max)+'%"></b></i><strong>'+item.score+'</strong><small>'+esc([...item.keywordHits,...item.metricHits,...item.companyHits].slice(0,4).join(' · ')||'NO SIGNAL')+'</small></div>').join('');
    const diff=plan.diff;
    el('v216DiffSummary').innerHTML=listBlock('新增节点',diff.addedNodes,'added')+listBlock('移除节点',diff.removedNodes,'removed')+listBlock('更新节点',diff.updatedNodes,'updated')+listBlock('共享节点',diff.sharedNodes,'shared')+listBlock('不可用节点',diff.unavailableNodes,'unavailable')+listBlock('未映射字段',plan.unknownFields,'unknown');
    el('v216DiffLists').innerHTML='<div><span>公司解析</span><b>'+esc(plan.companies.matched.map((item)=>item.name).join(' · ')||plan.companies.candidate?.name||'NOT PROVIDED')+'</b><small>'+esc(plan.companies.candidate?.reason||'已登记公司不会跨领域复用')+'</small></div><div><span>计划哈希</span><b>'+esc(plan.planId)+'</b><small>'+esc(plan.reason)+'</small></div>';
    el('v216GateList').innerHTML=Object.entries(plan.gates).map(([key,value])=>'<div><span>'+esc(key.toUpperCase())+'</span><b class="'+className(value)+'">'+esc(value)+'</b></div>').join('');
    el('v216ApprovePlan').disabled=!plan.detectedDomain||!plan.mappings.some((row)=>row.status==='MATCHED');
    el('v216ApprovePlan').textContent=state.planApproved?'差异计划已确认':'确认网络差异';
  }
  function renderPackage(){
    el('v215PackageTree').textContent='domain-package/\n├── package_manifest.json\n├── domain.json\n├── data_snapshot.json\n├── metric_mapping.json\n├── company_adapters.json\n├── network_diff.json\n├── activation.json\n├── quality_report.json\n├── quarantine.json\n└── hashes.json';
    const built=state.packageBuild;
    el('v216PackageState').textContent=built?built.status:state.planApproved&&state.mappingApproved?'READY_TO_BUILD':'GATED';
    el('v215BuildPackage').disabled=!(state.planApproved&&state.mappingApproved);
    el('v216ActivatePackage').disabled=!(built?.activationAllowed&&state.plan?.executable);
    const active=window.NEXUS_V216_RUNTIME_IMPORT;
    el('v216ActiveImport').innerHTML=active?.status==='CANDIDATE_ACTIVE'?'<b>'+esc(active.packageId)+'</b><span>'+active.updatedNodeIds.length+' 个节点加载为候选快照</span><small>formal_ready=false · ABSTAIN</small>':'<b>NO ACTIVE IMPORT</b><span>当前运行使用冻结领域包</span>';
  }
  function renderTasks(){
    const tasks=state.tasks.length?state.tasks:[['LOAD_PACKAGE','SUCCEEDED',pkg.version],['RESOLVE_DOMAIN',state.plan?'PREVIEW':'QUEUED',state.plan?.planId||'等待数据'],['EVIDENCE_REVIEW','WAITING_REVIEW','缺少原文定位和快照哈希'],['REPLAY_RUN','QUEUED','历史快照尚未构建']];
    el('v215TaskQueue').innerHTML=tasks.map((row)=>'<div><span>'+esc(row[0]||row.type)+'</span><b>'+esc(row[1]||row.status)+'</b><small>'+esc(row[2]||row.detail||'')+'</small></div>').join('');
    el('v215TaskState').textContent=state.connector==='LOCAL CONNECTOR'?'CONNECTED':'LOCAL';
    const quarantine=[...state.quarantine];
    if(state.plan?.unknownFields.length)quarantine.push({code:'OUT_OF_SCOPE_FIELDS',reason:state.plan.unknownFields.join(' · ')});
    if(state.plan&&!state.plan.executable)quarantine.push({code:state.plan.reason,reason:'当前计划不能进入确定性金融引擎'});
    el('v215QuarantineCount').textContent=quarantine.length;
    el('v215Quarantine').innerHTML=quarantine.length?quarantine.map((item)=>'<div><b>'+esc(item.code)+'</b><span>'+esc(item.reason)+'</span></div>').join(''):'<div><b>NO ACTIVE CONFLICT</b><span>证据缺口仍由研究门禁逐项显示</span></div>';
  }
  function packagePayload(){
    const plan=state.plan;
    const catalog=resolver.catalogs[plan.detectedDomain];
    const packageId=plan.detectedDomain+'-'+plan.planId.toLowerCase()+'-'+Date.now();
    return{manifest:{packageId,schemaVersion:'standard-domain-package-1.1.0',domainId:plan.detectedDomain,domainVersion:catalog.status==='SUPPORTED'?'existing-domain-overlay-1.0.0':'candidate-domain-0.1.0',parentVersion:'2.15.3-frozen',dataCutoff:window.NEXUS_V25_RUN.dataCutoff,createdAt:new Date().toISOString(),sourceHash:state.sourceMeta?.sourceHash||null,formalReady:false},domain:plan.targetDomain,mapping:{status:state.mappingApproved?'HUMAN_CONFIRMED':'PENDING_REVIEW',rows:state.mappings},snapshot:{source:state.sourceMeta,profile:state.profileRows,entityHints:state.entityHints,cutoff:window.NEXUS_V25_RUN.dataCutoff,valueStatus:'PENDING_REVIEW'},companyAdapters:{matched:plan.companies.matched,candidate:plan.companies.candidate,status:plan.companies.candidate?'COMPANY_ADAPTER_REQUIRED':'MATCHED_OR_NOT_PROVIDED'},compiler:{...plan,reviewStatus:state.planApproved?'HUMAN_CONFIRMED':'PENDING_REVIEW'},activation:{...plan.activation,allowed:plan.activation.allowed&&state.planApproved&&state.mappingApproved},quality:{contract:window.NEXUS_V25_RUN.contractCheck(),causalConclusion:'ABSTAIN',formalReady:false,cutoffStatus:state.profile?.cutoff_status||'NOT_IDENTIFIED'},quarantine:state.quarantine};
  }
  async function health(){try{const response=await api.request('/api/health');if(response.state!=='ready')throw new Error(response.error?.message||'HEALTH_CHECK_FAILED');const data=response.data;state.connector='LOCAL CONNECTOR';if(!state.sourceMeta)state.profile={connector_version:data.version,bind:data.bind,read_only:data.readOnly,supported_files:data.fileTypes.join(' / '),ai_mode:data.aiMode};}catch(error){state.connector='STATIC MODE';}render();}
  async function profilePostgres(){
    el('v215ConnectorState').textContent='PROFILING';
    try{
      const response=await api.profileSource({sourceType:'postgresql',preset:'workspace',cutoff:window.NEXUS_V25_RUN.dataCutoff});
      if(response.state!=='ready'&&response.state!=='partial')throw new Error(response.error?.message||'SOURCE_PROFILE_FAILED');
      const data=response.data;
      state.connector='LOCAL CONNECTOR';state.profile=data.summary;state.profileRows=data.profile||[];state.entityHints=[];state.sourceMeta={sourceType:'POSTGRESQL',fileName:'workspace-postgresql',snapshot:'READ_ONLY_PROFILE',sourceHash:null};state.tasks=data.tasks||state.tasks;analyze();
      if(data.sourceId)window.dispatchEvent(new CustomEvent('nexus:source-analyzed',{detail:{sourceId:data.sourceId,mappings:data.mappings||[],metricCatalog:data.metricCatalog||[],sourceType:'DATABASE',tables:['asharebalancesheet','asharecashflow','ashareincome']}}));
    }catch(error){state.profile={error:error.message,write_operations:'NONE'};render();}
  }
  async function upload(file){
    if(!file)return;
    const bytes=new Uint8Array(await file.arrayBuffer());let binary='';bytes.forEach((value)=>binary+=String.fromCharCode(value));
    try{
      const response=await api.profileSource({sourceType:'file',name:file.name,content:btoa(binary),cutoff:window.NEXUS_V25_RUN.dataCutoff});
      if(response.state!=='ready'&&response.state!=='partial')throw new Error(response.error?.message||'SOURCE_PROFILE_FAILED');
      const data=response.data;
      state.connector='LOCAL CONNECTOR';state.profile=data.summary;state.profileRows=data.profile||[];state.entityHints=data.entityHints||[];state.sourceMeta={sourceType:data.summary.source_type,fileName:data.summary.file_name,snapshot:data.snapshot,sourceHash:data.sourceHash};state.tasks=data.tasks||state.tasks;analyze();
      if(data.sourceId)window.dispatchEvent(new CustomEvent('nexus:source-analyzed',{detail:{sourceId:data.sourceId,mappings:data.mappings||[],metricCatalog:data.metricCatalog||[],sourceType:'FILE',tables:[]}}));
    }catch(error){state.profile={error:error.message};render();}
  }
  function demo(kind){
    const demos={
      ai:{fileName:'ai-supply-quarterly.csv',entityHints:['NVDA'],profile:[{column:'report_date',dtype:'date'},{column:'ticker',dtype:'string'},{column:'ai_capex',dtype:'float',candidateValue:-30},{column:'hbm_supply',dtype:'float',candidateValue:50},{column:'cowos_capacity',dtype:'float',candidateValue:40}]},
      coal:{fileName:'coal-steel-operating.csv',entityHints:['601088.SH'],profile:[{column:'ann_dt',dtype:'date'},{column:'security_code',dtype:'string'},{column:'coking_coal_price',dtype:'float',candidateValue:-20},{column:'steel_demand',dtype:'float',candidateValue:-15},{column:'port_inventory',dtype:'float',candidateValue:8.2}]},
      ev:{fileName:'new-energy-vehicle.csv',entityHints:['300750.SZ'],profile:[{column:'report_date',dtype:'date'},{column:'ticker',dtype:'string'},{column:'lithium_price',dtype:'float',candidateValue:-30},{column:'battery_capacity',dtype:'float',candidateValue:18},{column:'ev_demand',dtype:'float',candidateValue:12}]}
    };
    const sample=demos[kind];state.profile={source_type:'DEMO',file_name:sample.fileName,rows_profiled:12,columns:sample.profile.length,cutoff_status:'PASS_OR_NOT_IDENTIFIED'};state.profileRows=sample.profile;state.entityHints=sample.entityHints;state.sourceMeta={sourceType:'DEMO',fileName:sample.fileName,snapshot:'IN_MEMORY_DEMO',sourceHash:resolver.stableHash(sample)};state.tasks=[['PROFILE_SOURCE','SUCCEEDED','示例字段画像完成'],['RESOLVE_DOMAIN','PREVIEW','等待人工确认']];analyze();
  }
  async function buildPackage(){
    if(!(state.mappingApproved&&state.planApproved))return;
    const payload=packagePayload();
    try{
      const response=await api.buildPackage(payload);if(response.state!=='ready')throw new Error(response.error?.message||'PACKAGE_BUILD_FAILED');const data=response.data;
      state.packageBuild=data;state.tasks=data.tasks||state.tasks;state.quarantine=data.quarantine||state.quarantine;render();
    }catch(error){state.quarantine.push({code:'PACKAGE_BUILD_FAILED',reason:error.message});render();}
  }
  function activate(){
    if(!state.packageBuild?.activationAllowed||!state.plan?.executable)return;
    const record={status:'ACTIVATED',packageId:state.packageBuild.packageId,plan:state.plan,activatedAt:new Date().toISOString()};
    localStorage.setItem('nexus-v2.17-active-import',JSON.stringify(record));
    const url=new URL(window.location.href);url.searchParams.set('domain',state.plan.detectedDomain);url.searchParams.set('view','world');url.searchParams.set('importRun',state.packageBuild.packageId);url.searchParams.set('v','2.17.0');window.location.assign(url);
  }
  async function testAi(){const provider=el('v215AiProvider').value;if(provider==='disabled'){el('v215AiState').textContent='AI 已关闭 · 规则与人工映射仍可使用';return;}const button=el('v215TestAi'),original=button.textContent,payload={provider,baseUrl:el('v215AiBaseUrl').value,model:el('v215AiModel').value,apiKey:el('v215AiKey').value,timeoutSeconds:Number(el('v218AiTimeout')?.value||30)},labels={AUTH_FAILED:'认证失败，请检查 API Key',MODEL_NOT_FOUND:'模型或接口不存在',RATE_LIMITED:'请求频率受限',NETWORK_ERROR:'网络无法连接到提供商',TIMEOUT:'连接测试超时',INVALID_RESPONSE:'聊天接口或响应格式不兼容'};button.disabled=true;button.textContent='正在验证聊天接口…';el('v215AiState').textContent='正在验证模型列表与实际生成';try{const response=await api.ai.testSession(payload);const normalizedUrl=response.data?.config?.baseUrl;if(normalizedUrl)el('v215AiBaseUrl').value=normalizedUrl;const code=response.data?.status||response.error?.code;el('v215AiState').textContent=code==='CONNECTED'&&response.data?.chatVerified?'已连接 · CHAT VERIFIED':(labels[code]||response.data?.detail||response.error?.message||'AI 连接失败')+(code?' · '+code:'');window.dispatchEvent(new CustomEvent('nexus:ai-state',{detail:response}));}catch(error){el('v215AiState').textContent='AI 连接失败 · CLIENT_ERROR';}finally{button.disabled=false;button.textContent=original;el('v215AiKey').value='';}}
  function renderValuationMode(){
    if(bridge.state.networkMode==='standalone')return;
    const result=currentValuation();if(!result)return;
    el('v215ValuationMode').textContent='MARKET_CALIBRATED_SCENARIO';el('v215ValuationModeNote').textContent='当前市场定价上施加经营、倍数和现金流冲击；不是独立目标价';el('v215MarketGate').textContent='PARTIAL · IMPLIED SHARES';el('v215IntrinsicGate').textContent='ABSTAIN · INDEPENDENT BASELINE MISSING';el('v213MarketUpside').textContent='ABSTAIN';el('v213MarketUpside').className='';el('v213MarketUpside').nextElementSibling.textContent='稀释股数原文与独立基准未闭环';
    const results=valuation.evaluateAll(bridge.current()?.base.companies||[]),byId=new Map((bridge.current()?.base.companies||[]).map((item)=>[item.id,item]));let sorted=[...results];if(state.rankMode==='amount'&&runtime.id==='coal-steel')sorted.sort((a,b)=>b.valueChangeAmount-a.valueChangeAmount);else sorted.sort((a,b)=>b.valueChangePct-a.valueChangePct);let controls=document.getElementById('v215RankControls');if(!controls){controls=document.createElement('div');controls.id='v215RankControls';controls.className='v215-rank-controls';el('companyRanking').before(controls);controls.addEventListener('click',(event)=>{const button=event.target.closest('[data-v215-rank]');if(!button||button.disabled)return;state.rankMode=button.dataset.v215Rank;renderValuationMode();});}controls.innerHTML='<span>公司排序</span><button data-v215-rank="changePct" class="'+(state.rankMode==='changePct'?'active':'')+'">变化比例</button><button data-v215-rank="amount" '+(runtime.id!=='coal-steel'?'disabled title="多币种金额不可直接比较"':'')+' class="'+(state.rankMode==='amount'?'active':'')+'">变化金额</button><button disabled title="稀释股数来源门禁未通过">相对市值空间</button>';
    el('companyRanking').innerHTML=sorted.map((item,index)=>{const company=byId.get(item.companyId);return'<button class="rank-company '+(item.companyId===bridge.state.selectedCompany?'active':'')+'" data-rank-company="'+item.companyId+'"><span>#'+(index+1)+' '+esc(company.ticker)+'</span><b class="'+(item.valueChangePct<0?'negative':'positive')+'">'+(state.rankMode==='amount'?money(item.valueChangeAmount,item):pct(item.valueChangePct))+'</b><small>'+esc(company.name)+' · '+money(item.valueChangeAmount,item)+'</small></button>';}).join('');
    const coverage=results.filter((item)=>item.currentMarketCap!=null).length;el('v27IndustryValue').textContent=coverage+' / '+results.length;el('v27IndustryValue').previousElementSibling.textContent='当前市值候选覆盖';el('industryBase').textContent='市场事实仍待股价、股数和日期原文闭环';
  }
  function render(){renderProfile();renderMappings();renderResolution();renderPackage();renderTasks();renderValuationMode();}
  function acceptDatabaseProfile(data, sourceMeta){
    state.connector='LOCAL CONNECTOR';
    state.profile=data.summary||{};
    state.profileRows=data.profile||[];
    state.entityHints=data.entityHints||[];
    state.sourceMeta=sourceMeta;
    state.tasks=data.tasks||state.tasks;
    analyze();
  }

  el('v215ProfilePostgres').addEventListener('click',profilePostgres);
  el('v215SourceFile').addEventListener('change',(event)=>upload(event.target.files[0]));
  document.querySelectorAll('[data-v216-demo]').forEach((button)=>button.addEventListener('click',()=>demo(button.dataset.v216Demo)));
  el('v216ImportIntent').addEventListener('change',(event)=>{state.intent=event.target.value;analyze();});
  el('v216CompanyHint').addEventListener('change',(event)=>{state.companyHint=event.target.value.trim();analyze();});
  el('v216Reanalyze').addEventListener('click',()=>{state.companyHint=el('v216CompanyHint').value.trim();analyze();});
  el('v215ApproveMappings').addEventListener('click',()=>{if(!state.mappings.some((row)=>row.status==='MATCHED'))return;state.mappingApproved=true;render();});
  el('v216ApprovePlan').addEventListener('click',()=>{if(!state.plan?.detectedDomain)return;state.planApproved=true;render();});
  el('v215BuildPackage').addEventListener('click',buildPackage);
  el('v216ActivatePackage').addEventListener('click',activate);
  el('v215TestAi').addEventListener('click',testAi);
  document.addEventListener('nexus:render',renderValuationMode);
  document.addEventListener('click',(event)=>{if(event.target.closest('[data-rank-company]'))setTimeout(renderValuationMode,0);});
  el('companySelect').addEventListener('change',()=>setTimeout(renderValuationMode,0));
  const requestedDemo=new URLSearchParams(window.location.search).get('demo');
  health();
  if(['ai','coal','ev'].includes(requestedDemo))demo(requestedDemo);else render();
  window.NEXUS_V216_WORKBENCH={state,render,analyze,demo,packagePayload,activate,acceptDatabaseProfile};
}());
