(function(){
  const api=window.NEXUS_API_CLIENT, el=(id)=>document.getElementById(id);
  if(!api||!el('v218PipelineState'))return;
  if(el('v218AiTimeout')&&el('v218AiTimeout').value==='30')el('v218AiTimeout').value='60';
  const state={sourceId:null,mappings:[],catalog:[],values:[],plan:null,scenarioId:null,result:null,stage:0,busy:false,networkIntent:'CREATE_NEW_NETWORK',aiRetry:false,precompiledAdapter:null,precompiledNetwork:null};
  const esc=(v)=>String(v??'').replace(/[&<>"']/g,(c)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const zh={UNRESOLVED:'尚未识别',PENDING_REVIEW:'等待审核',CONFIRMED:'已确认',IGNORED:'不纳入当前领域',PARTIAL:'部分结果',CALCULATED:'已计算',DATA_MISSING:'数据缺失',ACTIVE:'已激活'};
  function stage(i,text){state.stage=Math.max(state.stage,i);el('v218PipelineState').textContent=text;[...el('v218Steps').children].forEach((n,x)=>n.classList.toggle('active',x<=state.stage));}
  function errorText(r){const code=r?.error?.code||r?.data?.status,raw=r?.error?.message||r?.data?.detail||'';if(raw.startsWith('CONFIRMED_CONTROL_FIELDS_REQUIRED'))return'缺少已确认的实体标识或报告期；请确认表级“自动行标识”和“报告期候选” · '+raw;if(raw.startsWith('CUTOFF_MAPPING_REQUIRED'))return'缺少公告日期或同步截止日策略 · '+raw;const labels={AUTH_FAILED:'认证失败',MODEL_NOT_FOUND:'模型或接口不存在',RATE_LIMITED:'请求频率受限',NETWORK_ERROR:'网络无法连接',TIMEOUT:'请求超时',INVALID_RESPONSE:'响应格式无效',PERMISSION_DENIED:'权限不足',AI_NOT_CONNECTED:'AI会话未连接，请先在“任务治理”配置提供商并测试连接'};return(labels[code]||raw||'请求错误')+(code?' · '+code:'');}
  function aiState(id,text,kind=''){const node=el(id);if(!node)return;node.textContent=text;node.className='v218-ai-state '+kind;}
  function fail(r){state.busy=false;const message=errorText(r);el('v218PipelineState').textContent=message;if(el('v218NetworkDiff')&&state.plan){el('v218NetworkDiff').insertAdjacentHTML('afterbegin','<p class="v219-inline-error">'+esc(message)+'</p>');}renderMappings();return message;}
  function options(code){const pending=state.catalog.some((m)=>m.metricCode===code)?'':'<option value="" selected disabled>请选择标准指标</option>';return pending+state.catalog.map((m)=>'<option value="'+esc(m.metricCode)+'" '+(m.metricCode===code?'selected':'')+'>'+esc(m.metricName)+' · '+esc(m.metricCode)+'</option>').join('');}
  function mappingStatus(mapping){if(state.precompiledAdapter?.detected&&mapping.suggestedAction==='IGNORE')return'系统已排除';return mapping.suggestedAction==='IGNORE'&&mapping.status==='PENDING_REVIEW'?'建议忽略':zh[mapping.status]||mapping.status;}
  function mappingLabel(mapping){return mapping.columnName||mapping.sourceField||'未命名字段';}
  function mappingPath(mapping){const locator=mapping.sourceLocator||{};return[locator.database,mapping.schemaName||locator.schema,mapping.tableName||locator.table].filter(Boolean).join('.')||'当前数据源';}
  function sampleText(mapping){const values=mapping.sampleSummary?.sampleValues||[];return values.length?'样例：'+values.slice(0,3).map((value)=>String(value)).join(' / '):'样例未提供';}
  function mergeCandidate(item,candidate){
    Object.assign(item,candidate);
    const definition=candidate.metricDefinition;
    if(definition?.metricCode){const index=state.catalog.findIndex((metric)=>metric.metricCode===definition.metricCode);if(index>=0)state.catalog[index]={...state.catalog[index],...definition};else state.catalog.push(definition);}
  }
  function renderMappings(){
    const done=state.mappings.filter((m)=>m.status==='CONFIRMED').length,custom=state.mappings.filter((m)=>['CUSTOM_NUMERIC','AI_SEMANTIC'].includes(m.candidateSource)&&m.status!=='CONFIRMED').length,semantic=state.mappings.filter((m)=>m.candidateSource==='AI_SEMANTIC'&&m.status==='PENDING_REVIEW').length,q=el('v218MappingFilter').value.toLowerCase();
    const ignored=state.mappings.filter((m)=>m.suggestedAction==='IGNORE').length;const compiled=state.precompiledAdapter?.detected?' · 预编译表自动确认 '+Number(state.precompiledAdapter.autoConfirmed||0)+' · 系统排除 '+ignored+' 个辅助字段 · 仅 '+Number(state.precompiledAdapter.needsReview||0)+' 项需审核':'';el('v218MappingProgress').textContent=done+' / '+state.mappings.length+' 已确认'+compiled+(semantic?' · '+semantic+' 个AI中文候选':custom?' · '+custom+' 个自定义指标待确认':'');el('v218Sync').disabled=!done||state.busy;
    const reviewOnly=state.precompiledAdapter?.detected&&!q,sourceRows=reviewOnly?state.mappings.filter((m)=>!['CONFIRMED','IGNORED'].includes(m.status)):state.mappings;
    const rows=sourceRows.filter((m)=>!(state.precompiledAdapter?.detected&&m.suggestedAction==='IGNORE')&&(!q||([mappingLabel(m),mappingPath(m),m.metricCode,m.metricName].join(' ')).toLowerCase().includes(q))).slice(0,150);
    const empty=reviewOnly?'<p class="v218-empty">预编译网络字段已全部按确定性契约确认，无需逐列审核。输入字段名可查看具体映射。</p>':'<p class="v218-empty">没有字段。</p>';
    el('v218Mappings').innerHTML=rows.map((m)=>'<div class="v218-map-row" data-map="'+m.mappingId+'" data-ai="'+(['AI','AI_CACHE','LOCAL_PREFILTER','AI_SEMANTIC'].includes(m.candidateSource))+'"><div class="v219-map-source"><b>'+esc(mappingLabel(m))+'</b><strong>'+esc(m.metricName||'尚未识别')+'</strong><span>'+esc(mappingPath(m))+'</span><small>'+esc(m.candidateSource)+' · '+Math.round(m.confidence*100)+'% · '+esc(m.reason)+'</small>'+(m.candidateSource==='AI_SEMANTIC'?'<small class="v219-sample">'+esc(sampleText(m))+' · 候选层级 '+esc(m.metricDefinition?.networkLayer||'标准层级')+'</small>':'')+'</div><select data-select>'+options(m.metricCode)+'</select><i>'+esc(mappingStatus(m))+'</i><div class="v218-map-actions"><button data-action="confirm" '+(m.suggestedAction==='IGNORE'?'disabled title="该候选建议忽略，请先手工选择指标后再确认"':'')+'>确认</button><button data-action="ignore">忽略</button><button data-action="reset">恢复</button></div></div>').join('')||empty;
  }
  function renderValues(){el('v218ValueCount').textContent=state.values.length+' 条';const empty=state.precompiledNetwork?'<p class="v-empty">这是结构化网络数据：指标值已绑定到网络节点，不另外生成普通指标列表。</p>':'<p class="v-empty">没有标准指标值。</p>';el('v218Values').innerHTML=state.values.slice(0,120).map((v)=>'<div class="v218-value"><span>'+esc(v.entityCode)+' · '+esc(v.metricName)+'</span><b>'+Number(v.value).toLocaleString('zh-CN')+' '+esc(v.currency||v.unit||'')+'</b><small>'+esc(v.reportPeriod)+' · '+esc(v.sourceTable)+'.'+esc(v.sourceColumn)+' · '+esc(v.evidenceId)+'</small></div>').join('')||empty;}
  function renderNetwork(){
    const d=state.plan?.diff;if(!d)return;
    const standalone=state.plan.mode==='CREATE_NEW_NETWORK';
    const stats=[[standalone?'独立节点':'新增节点',d.addedNodes.length],['更新节点',d.updatedNodes.length],[standalone?'替换底图':'移除节点',d.removedNodes.length],['共享节点',d.sharedNodes.length],['证据缺口',d.evidenceGaps.length],['公司缺口',d.companyAdapterGaps.length]];
    const companies=d.updatedNodes.concat(d.addedNodes);
    const layerSummary=standalone?(state.plan.layerLabels||[]).map((layer)=>'<span>'+esc(layer.label)+'<small>'+state.plan.graph.nodes.filter((node)=>node.layer===layer.id).length+' 节点</small></span>').join('<i>→</i>'):'<span>焦煤价格</span><i>→</i><span>原料成本</span><i>→</i><span>高炉利润</span><i>→</i><div>'+companies.filter((n)=>n.layer==='company').map((n)=>'<b>'+esc(n.label)+'<small>'+esc(n.companyModel||n.status)+'</small></b>').join('')+'</div>';
    const candidateEdges=(state.plan.graph?.edges||[]).filter((edge)=>edge.status==='CANDIDATE');
    const edgeReview=candidateEdges.length?'<div class="v219-edge-review"><b>待确认的情景传播关系</b>'+candidateEdges.map((edge)=>'<label><input type="checkbox" data-v219-edge="'+esc(edge.edgeId)+'"><span>'+esc(state.plan.graph.nodes.find((node)=>node.nodeId===edge.sourceNodeId)?.label||edge.sourceNodeId)+' → '+esc(state.plan.graph.nodes.find((node)=>node.nodeId===edge.targetNodeId)?.label||edge.targetNodeId)+'</span><small>'+esc(edge.direction)+' · 权重 '+Number(edge.weight).toFixed(2)+' · 滞后 '+Number(edge.lagDays||0)+' 天 · 置信度 '+Math.round(Number(edge.confidence||0)*100)+'%<br>'+esc(edge.mechanism)+'</small></label>').join('')+'</div>':'';
    const boundary=standalone?(candidateEdges.length?'勾选你认可的关系后确认网络；只有已确认关系进入确定性推演。':'当前只有数据谱系和会计结构。可点击“AI生成关系候选”，再由你确认后开放情景传播。'):'';
    el('v218NetworkDiff').innerHTML='<div class="v219-plan-identity"><b>'+esc(state.plan.networkName||'未命名网络')+'</b><span>'+esc(state.plan.networkKind||'DOMAIN_OVERLAY')+' · '+esc(state.plan.outputLevel||'MODEL_GATED')+' · 因果 '+esc(state.plan.causalStatus||'ABSTAIN')+'</span></div><div class="v218-diff-stats">'+stats.map((x)=>'<div><span>'+x[0]+'</span><b>'+x[1]+'</b></div>').join('')+'</div><div class="v218-network-flow '+(standalone?'standalone':'')+'">'+layerSummary+'</div>'+edgeReview+(standalone?'<p class="v219-boundary">'+boundary+'</p>':'');
  }
  function renderResult(){
    const r=state.result;if(!r)return;
    const rows=(r.companyResults||[]).map((c)=>'<tr><td><b>'+esc(c.companyName)+'</b><small>'+esc(c.entityCode)+' · '+esc(c.companyModel)+'</small></td><td>'+esc(c.baselineRevenue==null?'数据缺失':Number(c.baselineRevenue).toLocaleString('zh-CN'))+'</td><td>'+esc(c.scenarioRevenue==null?'数据缺失':Number(c.scenarioRevenue).toLocaleString('zh-CN'))+'</td><td class="'+(c.changePercent>=0?'positive':'negative')+'">'+Number(c.changePercent).toFixed(2)+'%</td><td>'+Math.round(c.confidence*100)+'%</td><td>'+esc(zh[c.status]||c.status)+'</td></tr>').join('');
    const ledger=(r.calculationLedger||[]).map((x)=>'<li><b>'+esc(x.edgeId)+'</b><span>'+esc(x.formula)+' · 滞后 '+x.lagDays+' 天</span><small>'+esc(JSON.stringify(x.inputs))+' → '+esc(x.output)+'</small></li>').join('');
    el('v218Result').innerHTML='<div class="v218-result-head"><b>'+esc(zh[r.status]||r.status)+'</b><span>公式 '+esc(r.formulaVersion)+' · 截止 '+esc(r.dataCutoff)+' · 证据 '+(r.evidenceIds||[]).length+' 条</span></div><table><thead><tr><th>公司</th><th>基准收入</th><th>情景收入</th><th>变化</th><th>置信度</th><th>状态</th></tr></thead><tbody>'+rows+'</tbody></table><details><summary>查看计算过程与影响机制</summary><ol>'+ledger+'</ol></details>';
  }
  async function mappingAction(row,action){
    const item=state.mappings.find((m)=>m.mappingId===row.dataset.map);if(!item)return;
    const r=await api.mappings.confirm(item.mappingId,{action,metricCode:row.querySelector('[data-select]').value});
    if(r.state!=='ready')return fail(r);mergeCandidate(item,r.data.mapping);state.values=[];state.plan=null;renderMappings();stage(1,'映射审核中');
  }
  window.addEventListener('nexus:source-analyzed',(event)=>{
    const d=event.detail||{};Object.assign(state,{sourceId:d.sourceId,mappings:d.mappings||[],catalog:d.metricCatalog||[],values:[],plan:null,result:null,stage:1,precompiledAdapter:d.precompiledAdapter||null,precompiledNetwork:null});
    const standardTables=new Set(['asharebalancesheet','asharecashflow','ashareincome']);
    state.networkIntent=d.networkIntent||el('v219NetworkMode').value;
    if(state.networkIntent==='CREATE_NEW_NETWORK'||(d.sourceType==='DATABASE'&&(d.tables||[]).some((table)=>!standardTables.has(String(table).toLowerCase())))){
      el('v218Entities').value='';
      el('v218Entities').placeholder='留空读取当前表中的全部实体';
    }
    stage(1,d.precompiledAdapter?.detected?'预编译网络结构已识别；仅检查模糊字段后即可同步':'等待逐字段确认');renderMappings();renderValues();
  });
  el('v218Mappings').addEventListener('click',(event)=>{const b=event.target.closest('[data-action]');if(b)mappingAction(b.closest('[data-map]'),b.dataset.action);});
  el('v218MappingFilter').addEventListener('input',renderMappings);
  el('v218ConfirmRules').addEventListener('click',async()=>{
    const items=state.mappings.filter((m)=>['RULE','CUSTOM_NUMERIC','TABLE_ADAPTER','AI_SEMANTIC'].includes(m.candidateSource)&&m.suggestedAction!=='IGNORE'&&m.status!=='CONFIRMED'&&!(m.candidateSource==='CUSTOM_NUMERIC'&&/^(column|col|c)[_-]?\d+$/i.test(mappingLabel(m))));state.busy=true;renderMappings();
    for(const item of items){const r=await api.mappings.confirm(item.mappingId,{action:'confirm',metricCode:item.metricCode});if(r.state!=='ready')return fail(r);mergeCandidate(item,r.data.mapping);}
    state.busy=false;stage(1,'可用字段语义与表参数已确认');renderMappings();
  });
  el('v218AskAi').addEventListener('click',async()=>{
    if(!state.sourceId){aiState('v218AiMapState','请先画像数据源','error');return}
    const button=el('v218AskAi');state.aiRetry=false;button.disabled=true;button.textContent='后台识别中…';aiState('v218AiMapState','正在提交后台任务','busy');stage(1,'AI 映射任务正在后台运行');
    try{
      const started=await api.sources.startAiMappingJob(state.sourceId);
      if(started.state!=='ready'){const message=fail(started);aiState('v218AiMapState',message,'error');return}
      state.aiJobId=started.data.jobId;let job=started.data;
      while(!['SUCCEEDED','PARTIAL','FAILED'].includes(job.status)){
        const strategy=job.batchSize?' · '+Number(job.batchSize)+'字段/批 · '+Number(job.maxWorkers||1)+'路并发 · 单批最长'+Number(job.timeoutSeconds||30)+'秒':'';
        const localDone=Number(job.localResolvedFields||0)+Number(job.localSuggestedIgnore||0),routing=job.type==='AI_SEMANTIC_PROFILE'?' · 本地完成 '+localDone+' · AI排队 '+Number(job.aiQueuedFields||0):'';
        aiState('v218AiMapState','进度 '+Number(job.processedFields||0)+' / '+Number(job.totalFields||0)+' · 批次 '+Number(job.completedBatches||0)+' / '+Number(job.totalBatches||0)+routing+strategy,'busy');
        await new Promise((resolve)=>setTimeout(resolve,800));
        const polled=await api.ai.mappingJob(state.aiJobId);
        if(!['ready','partial'].includes(polled.state)){const message=fail(polled);aiState('v218AiMapState',message,'error');return}
        job=polled.data;
        for(const candidate of job.candidates||[]){const item=state.mappings.find((mapping)=>mapping.sourceField===candidate.sourceField);if(item)mergeCandidate(item,candidate);}
        renderMappings();
      }
      const failed=(job.errors||[]).reduce((sum,item)=>sum+Number(item.fieldCount||0),0),generated=(job.candidates||[]).filter((item)=>item.candidateSource==='AI_SEMANTIC').length,localResolved=Number(job.localResolvedFields||0),localIgnored=Number(job.localSuggestedIgnore||0),available=(job.candidates||[]).length,errorSummary=(job.errors||[]).map((item)=>item.code+' '+Number(item.fieldCount||0)+'字段').join(' / ');
      const localSummary=job.type==='AI_SEMANTIC_PROFILE'?' · 本地识别 '+localResolved+' 个 · 空值跳过 '+localIgnored+' 个':'';
      const summary=(job.type==='AI_SEMANTIC_PROFILE'?'AI中文语义候选 ':'字段映射候选 ')+'已生成 '+generated+' 个'+localSummary+' · 可审核 '+available+' 个 · 已处理 '+Number(job.processedFields||0)+' / '+Number(job.totalFields||0)+(failed?' · 失败 '+failed+' 个（'+errorSummary+'）':' · 等待人工确认');
      state.aiRetry=job.status==='PARTIAL'&&failed>0;aiState('v218AiMapState',summary,job.status==='SUCCEEDED'?'success':generated?'busy':'error');stage(1,job.status==='SUCCEEDED'?'AI 已生成中文语义候选，请确认后再同步':generated?'部分批次失败，已保留成功候选；可重试剩余字段':'AI 批次未完成，请重试剩余字段');
    }catch(error){state.aiRetry=true;aiState('v218AiMapState','客户端异常 · '+error.message,'error');}
    finally{button.disabled=false;button.textContent=state.aiRetry?'重试剩余字段':'AI读取样例并生成中文语义'}
  });
  el('v218Sync').addEventListener('click',async()=>{
    state.busy=true;renderMappings();el('v218Cancel').disabled=false;stage(2,'正在读取实际数据');
    const body={dataCutoff:el('v218Cutoff').value,entityCodes:el('v218Entities').value.split(',').map((v)=>v.trim()).filter(Boolean),rowLimit:Number(el('v218RowLimit').value)};
    const r=await api.sources.sync(state.sourceId,body);state.busy=false;el('v218Cancel').disabled=true;if(!['ready','partial'].includes(r.state))return fail(r);
    const compiled=r.data.precompiledNetwork,columnar=r.data.precompiledColumnar,prepared=compiled||columnar;state.precompiledNetwork=compiled||null;
    const tableRows=(r.data.tableRoles||[]).map((item)=>'<div class="v219-table-role"><b>'+esc(item.table)+'</b><span>'+esc(item.role)+' · '+esc(item.status)+'</span><small>'+Number(item.rowsRead||0)+' 行'+(item.missing?.length?' · 缺少 '+esc(item.missing.join('、')):'')+(item.detail?' · '+esc(item.detail):'')+'</small></div>').join('');
    const networks=(r.data.availableNetworks||[]).map((item)=>'<button type="button" class="v219-network-choice" data-source-network="'+esc(item.networkId)+'"><b>'+esc(item.networkName||item.networkId)+'</b><span>'+esc(item.validationStatus)+' · '+Number(item.nodeCount||0)+' 节点 · '+Number(item.edgeCount||0)+' 关系'+(item.formalReady?' · 可推演':' · '+esc(item.outputLevel||'ABSTAIN'))+'</span></button>').join('');
    el('v218SyncSummary').innerHTML='<div><b>'+r.data.rowsRead+'</b><span>读取行</span></div><div><b>'+r.data.acceptedRows+'</b><span>接受行</span></div><div><b>'+r.data.rejectedRows+'</b><span>拒绝项</span></div><div><b>'+(compiled?compiled.nodeCount:r.data.metricValuesCreated)+'</b><span>'+(compiled?'预编译节点':'指标值')+'</span></div><small>快照 '+esc(r.data.sourceSnapshotId)+' · 截止门禁 '+esc(r.data.cutoffStatus)+' · '+esc(r.data.syncStatus||'READY')+(compiled?' · JSON网络已校验 · '+Number(compiled.edgeCount||0)+' 条连线':columnar?' · 列式网络已校验 · '+Number(columnar.rowCount||0)+' 个公司参数':'')+'</small>'+(tableRows?'<section class="v219-role-report"><b>逐表处理结果</b>'+tableRows+'</section>':'')+(networks?'<section class="v219-network-choices"><b>检测到多个网络，请选择编译对象</b>'+networks+'</section>':'');
    const values=await api.sources.metricValues(state.sourceId);if(values.state==='ready'){state.values=values.data.metricValues||[];renderValues();}
    el('v218CreatePlan').disabled=!r.data.metricValuesCreated&&!prepared;stage(2,compiled?'预编译节点与连线已校验，可直接生成网络':columnar?'标准指标和传播参数已校验，可直接生成网络':'实际数据已标准化');renderMappings();
  });
  el('v218Cancel').addEventListener('click',()=>api.sources.cancel(state.sourceId));
  el('v218SyncSummary').addEventListener('click',(event)=>{const button=event.target.closest('[data-source-network]');if(!button)return;state.sourceNetworkId=button.dataset.sourceNetwork;[...el('v218SyncSummary').querySelectorAll('[data-source-network]')].forEach((item)=>item.classList.toggle('selected',item===button));stage(2,'已选择网络 '+state.sourceNetworkId+'，可以编译');});
  function applyIntent(reset=true){
    const mode=el('v219NetworkMode').value,standalone=mode==='CREATE_NEW_NETWORK',replace=mode==='REPLACE_EXISTING';
    state.networkIntent=mode;
    document.body.dataset.networkIntent=mode;
    const defaultEntities='601088.SH,601225.SH,600188.SH,600019.SH,000708.SZ';
    if(standalone)el('v218Entities').value='';
    else if(!el('v218Entities').value.trim())el('v218Entities').value=defaultEntities;
    const workflow=[...document.querySelectorAll('.v215-workflow>div')];
    if(workflow[2])workflow[2].innerHTML=standalone?'<i>03</i><b>网络语义</b><span>来源指标 / 六层布局</span>':'<i>03</i><b>当前领域</b><span>行业候选评分</span>';
    el('v219ModeNote').textContent=standalone?'先按新网络标准画像：只识别通用维度和本次来源指标，不加载焦煤—钢铁指标目录。':replace?'按当前领域标准画像；同步值覆盖当前快照，保留领域节点、公式与已确认关系。':'按当前领域标准画像；已确认字段作为新增或更新内容进入当前网络。';
    el('v219IntentSummary').textContent=standalone?'创建全新网络 · 不继承当前行业节点':replace?'覆盖当前网络数据 · 保留当前领域结构':'增加到当前网络 · 使用当前领域标准';
    el('v218ActivatePlan').textContent=standalone?'打开新网络':'激活网络';
    el('v218ScenarioControls').hidden=standalone;el('v219ScenarioIntentNote').hidden=!standalone;
    if(reset&&state.sourceId){Object.assign(state,{mappings:[],catalog:[],values:[],plan:null,result:null,stage:0});renderMappings();renderValues();el('v218CreatePlan').disabled=true;stage(0,'导入目标已改变，请重新画像选定表');}
    window.dispatchEvent(new CustomEvent('nexus:intent-changed',{detail:{networkIntent:mode}}));
  }
  el('v219NetworkMode').addEventListener('change',()=>applyIntent(true));
  el('v218CreatePlan').addEventListener('click',async()=>{
    const mode=state.networkIntent,networkName=el('v219NetworkName').value.trim();
    const r=await api.networkPlans.create({sourceId:state.sourceId,sourceNetworkId:state.sourceNetworkId||null,domainId:mode==='CREATE_NEW_NETWORK'?'generated-financial':'coal-steel',mode,networkName});if(r.state!=='ready')return fail(r);
    state.plan=r.data;el('v218PlanState').textContent='等待确认';el('v218GenerateEdges').disabled=state.plan.mode!=='CREATE_NEW_NETWORK';el('v218ConfirmPlan').disabled=false;renderNetwork();stage(3,'网络差异等待确认');
  });
  el('v218GenerateEdges').addEventListener('click',async()=>{
    if(!state.plan)return;el('v218GenerateEdges').disabled=true;el('v218PlanState').textContent='AI 正在生成候选关系';
    const r=await api.networkPlans.aiEdges(state.plan.networkPlanId);if(r.state!=='ready'){el('v218GenerateEdges').disabled=false;return fail(r)}
    state.plan.graph=state.plan.graph||{nodes:[],edges:[]};state.plan.graph.edges.push(...(r.data.candidates||[]));renderNetwork();el('v218PlanState').textContent=r.data.generationMode==='LOCAL_RULES'?'本地规则候选等待勾选':'AI关系候选等待勾选';stage(3,r.data.generationMode==='LOCAL_RULES'?'本地规则已生成候选关系，请确认方向、权重和机制':'AI 关系只是候选，请人工确认方向、权重和机制');
  });
  el('v218ConfirmPlan').addEventListener('click',async()=>{
    const confirmedEdgeIds=[...el('v218NetworkDiff').querySelectorAll('[data-v219-edge]:checked')].map((input)=>input.dataset.v219Edge);
    const r=await api.networkPlans.confirm(state.plan.networkPlanId,{confirmedEdgeIds});if(r.state!=='ready')return fail(r);
    state.plan=r.data;el('v218PlanState').textContent=state.plan.simulationReady?'已确认 · 可进行路径情景':'已确认 · 仅数据网络';el('v218GenerateEdges').disabled=true;el('v218ConfirmPlan').disabled=true;el('v218ActivatePlan').disabled=false;renderNetwork();
  });
  el('v218ActivatePlan').addEventListener('click',async()=>{
    if(!state.plan){return fail({error:{code:'NETWORK_PLAN_NOT_FOUND',message:'网络方案尚未编译，请先点击“编译网络方案”'}})}
    const bridge=window.NEXUS_V24_BRIDGE;
    if(!bridge?.applyRuntimeNetwork||(state.plan.mode==='CREATE_NEW_NETWORK'&&!bridge.applyStandaloneNetwork))return fail({error:{code:'CANVAS_BRIDGE_MISSING',message:'主画布运行时桥接未加载，请刷新页面后重试'}});
    const r=await api.networkPlans.activate(state.plan.networkPlanId);if(r.state!=='ready')return fail(r);
    state.plan=r.data;el('v218PlanState').textContent='正在载入主网络';el('v218ActivatePlan').disabled=true;el('v218Run').disabled=true;renderNetwork();stage(3,'网络已激活，正在刷新主画布');
    let nodes=await api.sandbox.nodes(),edges=await api.sandbox.edges();
    const graph=state.plan.graph||{nodes:[],edges:[]};
    if(nodes.state!=='ready')nodes={state:'ready',data:{}};
    if(edges.state!=='ready')edges={state:'ready',data:{}};
    const nodeData=nodes.data||{},edgeData=edges.data||{};
    const payload={networkPlanId:state.plan.networkPlanId,mode:nodeData.mode||state.plan.mode,networkKind:nodeData.networkKind||state.plan.networkKind,networkName:nodeData.networkName||state.plan.networkName,outputLevel:nodeData.outputLevel||state.plan.outputLevel,simulationReady:Boolean(state.plan.simulationReady),candidateScenarioReady:Boolean(state.plan.candidateScenarioReady||nodeData.candidateScenarioReady),layerLabels:nodeData.layerLabels||state.plan.layerLabels,nodes:nodeData.nodes?.length?nodeData.nodes:graph.nodes,edges:edgeData.edges?.length?edgeData.edges:graph.edges,causalGraph:nodeData.causalGraph||state.plan.causalGraph,candidateGraph:nodeData.candidateGraph||state.plan.candidateGraph,fullGraph:nodeData.fullGraph||graph,metricValues:state.values};
    const applied=state.plan.mode==='CREATE_NEW_NETWORK'?bridge.applyStandaloneNetwork?.(payload):bridge.applyRuntimeNetwork(payload);
    if(!applied.applied)return fail({error:{code:applied.reason||'NETWORK_APPLY_FAILED',message:'运行时网络不能应用到当前领域'}});
    const standalone=state.plan.mode==='CREATE_NEW_NETWORK',simulationReady=Boolean(applied.simulationReady),candidateReady=Boolean(applied.candidateScenarioReady);state.runtimeNetwork=applied;el('v218PlanState').textContent=standalone?'独立网络已打开':'已激活并载入主网络';el('v218Run').disabled=standalone;el('v218RunState').textContent=standalone?(candidateReady?'CANDIDATE SCENARIO · 点击上游节点改值':simulationReady?'SCENARIO READY · 点击上游节点改值':'ABSTAIN · 缺少可传播关系'):'等待运行';el('v218Result').innerHTML=standalone?'<div class="v219-exposure-result"><b>'+(candidateReady?'CANDIDATE SCENARIO PATH':'EXPOSURE_ONLY')+'</b><p>'+(candidateReady?'当前使用 AI 审核候选关系和代理权重进行条件传播；结果保持 ABSTAIN，不代表现实因果。':'独立网络已经生成，可以点击节点查看导入值、来源和关系机制。当前没有可传播关系。')+'</p></div>':'<p>输入情景后运行。</p>';stage(3,standalone?'新网络已生成 · 节点 '+applied.nodeCount+' · 关系 '+applied.edgeCount+(candidateReady?' · 候选可传播':simulationReady?' · 可推演':' · 仅数据谱系'):'主网络已刷新 · 更新 '+applied.updated.length+' · 新增 '+applied.added.length+' · 关系 '+applied.edgeCount);
    if(standalone)document.dispatchEvent(new CustomEvent('nexus:network-registered',{detail:{networkId:state.plan.networkPlanId,networkName:state.plan.networkName}}));
  });
  el('v218Run').addEventListener('click',async()=>{
    const changes=[{metricCode:'JM_PRICE',changePercent:Number(el('v218Shock').value),durationMonths:Number(el('v218Duration').value)}];stage(4,'确定性引擎计算中');
    const created=await api.scenarios.create({changes,dataCutoff:el('v218Cutoff').value});if(created.state!=='ready')return fail(created);state.scenarioId=created.data.scenarioId;
    const r=await api.scenarios.run(state.scenarioId,{changes});if(!['ready','partial'].includes(r.state))return fail(r);
    state.result=r.data;el('v218RunState').textContent=zh[r.data.status]||r.data.status;el('v218Explain').disabled=false;renderResult();stage(4,'确定性推演完成');
  });
  el('v218Explain').addEventListener('click',async()=>{
    if(!state.scenarioId){aiState('v218AiExplainState','请先运行情景','error');return}
    const button=el('v218Explain'),original=button.textContent;button.disabled=true;button.textContent='AI解释中…';aiState('v218AiExplainState','正在请求聊天接口','busy');
    try{
      const r=await api.scenarios.explain(state.scenarioId,{});
      if(!['ready','partial'].includes(r.state)){const message=fail(r);aiState('v218AiExplainState',message,'error');return}
      const d=r.data,box=document.createElement('div');box.className='v218-ai-explanation';box.innerHTML='<b>'+(d.status==='AI_NOT_CONNECTED'?'AI 未连接':'AI 候选解释')+'</b><p>'+esc(d.summary||d.detail||'暂无解释')+'</p><small>置信度 '+Math.round((d.confidence||0)*100)+'% · '+(d.evidence||[]).length+' 条证据引用 · 不改变计算结果</small>';
      el('v218Result').appendChild(box);aiState('v218AiExplainState',d.status==='AI_NOT_CONNECTED'?'AI 会话未连接':'解释已生成','success');stage(5,d.status==='AI_NOT_CONNECTED'?'AI 未连接，确定性结果仍可用':'AI 候选解释已生成');
    }catch(error){aiState('v218AiExplainState','客户端异常 · '+error.message,'error');}
    finally{button.disabled=false;button.textContent=original}
  });
  applyIntent(false);
  async function restoreWorkspace(){
    const response=await api.workspace?.get();
    if(response?.state!=='ready'||!response.data?.source)return;
    const data=response.data,source=data.source,plan=data.plan;
    el('v219NetworkMode').value=source.networkIntent||'CREATE_NEW_NETWORK';applyIntent(false);
    const restoredCompiled=source.snapshot?.precompiledNetwork||source.precompiledNetwork||null;
    Object.assign(state,{sourceId:source.sourceId,mappings:data.mappings||[],catalog:data.metricCatalog||[],values:data.metricValues||[],plan:plan||null,result:null,stage:0,networkIntent:source.networkIntent||'CREATE_NEW_NETWORK',precompiledAdapter:source.precompiledAdapter||null,precompiledNetwork:restoredCompiled});
    if(source.dataCutoff)el('v218Cutoff').value=String(source.dataCutoff).slice(0,10);
    if(plan?.networkName)el('v219NetworkName').value=plan.networkName;
    renderMappings();renderValues();
    const snapshot=source.snapshot||{};
    const compiled=snapshot.precompiledNetwork;if(source.status==='SYNCED')el('v218SyncSummary').innerHTML='<div><b>'+Number(snapshot.rowsRead||0)+'</b><span>读取行</span></div><div><b>'+Number(snapshot.acceptedRows||0)+'</b><span>接受行</span></div><div><b>'+Number(snapshot.rejectedRows||0)+'</b><span>拒绝项</span></div><div><b>'+(compiled?Number(compiled.nodeCount||0):Number(snapshot.metricValuesCreated||data.metricValueTotal||0))+'</b><span>'+(compiled?'预编译节点':'指标值')+'</span></div><small>已从当前本地会话恢复 · 密码未持久化'+(compiled?' · '+Number(compiled.edgeCount||0)+' 条连线':'')+'</small>';
    el('v218CreatePlan').disabled=!(data.metricValueTotal||compiled);
    if(plan){renderNetwork();el('v218ConfirmPlan').disabled=plan.status!=='PENDING_REVIEW';el('v218ActivatePlan').disabled=plan.status!=='CONFIRMED';el('v218PlanState').textContent=plan.status==='ACTIVE'?'已激活 · 刷新后恢复':plan.status==='CONFIRMED'?'已确认 · 等待打开':'等待确认';stage(3,'已恢复网络方案 · '+plan.networkName);}
    else if(compiled){stage(2,'已恢复已校验预编译网络 · '+compiled.nodeCount+' 节点 / '+compiled.edgeCount+' 连线');}
    else if(data.metricValueTotal){stage(2,'已恢复标准指标值 · '+data.metricValueTotal+' 条');}
    else{stage(1,'已恢复字段映射 · '+state.mappings.length+' 个');}
    aiState('v218AiMapState',data.aiSessionConnected?'AI会话仍有效':'AI密钥未持久化；如需分析请重新连接',data.aiSessionConnected?'success':'');
    window.dispatchEvent(new CustomEvent('nexus:workspace-restored',{detail:data}));
  }
  async function restoreSavedNetwork(){
    if(state.plan||!api.networks?.list)return;
    const listed=await api.networks.list();
    if(listed?.state!=="ready")return;
    const item=(listed.data.networks||[]).find((network)=>network.networkId==='PLAN-COALPOWER-V1');
    if(!item)return;
    const saved=await api.networks.get(item.networkId);
    if(saved?.state!=="ready"||!saved.data?.fullGraph?.nodes?.length)return;
    const applied=window.NEXUS_V24_BRIDGE?.applyStandaloneNetwork?.(saved.data);
    if(!applied?.applied)return;
    state.runtimeNetwork=applied;
    el("v218PlanState").textContent="已恢复已保存网络";
    stage(3,"已恢复煤炭-电力多链路网络 · "+applied.nodeCount+" 节点 / "+applied.edgeCount+" 关系");
  }  restoreWorkspace();
  restoreSavedNetwork();
  window.NEXUS_V218_PIPELINE={state,renderMappings,renderValues,renderNetwork,renderResult};
}());
