(function(root){
  const mock=root.NEXUS_API_MOCK;
  const query=new URLSearchParams(typeof location!=='undefined'?location.search:'');
  const mode=query.get('api')==='mock'?'mock':'http';
  let requestSequence=0;
  const clientId=(()=>{try{let value=sessionStorage.getItem('nexus-client-id');if(!value){value='CLIENT-'+crypto.randomUUID();sessionStorage.setItem('nexus-client-id',value)}return value}catch(error){return'CLIENT-EPHEMERAL'}})();
  const noSecret=(value)=>{if(!value||typeof value!=='object')return value;const copy=Array.isArray(value)?value.map(noSecret):{};if(!Array.isArray(value))Object.entries(value).forEach(([key,item])=>{if(!['password','apiKey','token','secret'].includes(key))copy[key]=noSecret(item)});return copy};
  async function request(path,options={}){
    const requestId='REQ-'+Date.now().toString(36)+'-'+(++requestSequence);
    if(mode==='mock')return{...(await mockRequest(path,options)),requestId};
    const headers={'Content-Type':'application/json','X-Client-Id':clientId,...(options.headers||{})};
    let response;
    try{response=await fetch(path,{...options,headers,cache:'no-store'});}catch(error){return{state:'error',error:{code:'NETWORK_ERROR',message:error.message,retryable:true},requestId}};
    let data=null;try{data=await response.json()}catch(error){data=null}
    if(response.status===401||response.status===403)return{state:'permission_denied',data,error:{code:'PERMISSION_DENIED',message:data?.detail||'权限不足'},requestId};
    if(!response.ok)return{state:'error',data,error:{code:data?.status||data?.error||'API_ERROR',message:data?.detail||'请求失败',retryable:response.status>=500},requestId};
    const state=data?.status==='PARTIAL'||data?.status==='ABSTAIN'?'partial':data?.status==='EMPTY'?'empty':'ready';
    return{state,data,requestId};
  }
  async function mockRequest(path,options){
    const body=options.body?JSON.parse(options.body):{};
    if(path==='/api/connections/test')return mock.connections.test(body);
    if(path==='/api/connections')return mock.connections.create(body);
    const tableMatch=path.match(/^\/api\/connections\/([^/]+)\/tables$/);if(tableMatch)return mock.connections.tables(tableMatch[1]);
    const sourceAnalyze=path.match(/^\/api\/sources\/([^/]+)\/analyze$/);if(sourceAnalyze)return mock.sources.analyze(sourceAnalyze[1],body);
    const sourceSync=path.match(/^\/api\/sources\/([^/]+)\/sync$/);if(sourceSync)return mock.sources.sync(sourceSync[1]);
    const sourceValues=path.match(/^\/api\/sources\/([^/]+)\/metric-values$/);if(sourceValues)return mock.sources.metricValues(sourceValues[1]);
    const sourceAi=path.match(/^\/api\/sources\/([^/]+)\/ai-mapping-candidates$/);if(sourceAi)return mock.sources.aiMappings(sourceAi[1],body);
    const sourceAiJob=path.match(/^\/api\/sources\/([^/]+)\/ai-mapping-jobs$/);if(sourceAiJob)return mock.ai.startMappingJob(sourceAiJob[1]);
    if(path==='/api/workspace')return mock.workspace.get();
    if(path==='/api/networks')return mock.networks.list();
    const networkMatch=path.match(/^\/api\/networks\/([^/]+)$/);if(networkMatch)return options.method==='DELETE'?mock.networks.delete(networkMatch[1]):mock.networks.get(networkMatch[1]);
    const aiJob=path.match(/^\/api\/ai\/mapping-jobs\/([^/]+)$/);if(aiJob)return mock.ai.mappingJob(aiJob[1]);
    const mappingMatch=path.match(/^\/api\/mappings\/([^/]+)\/confirm$/);if(mappingMatch)return mock.mappings.confirm(mappingMatch[1],body);
    if(path==='/api/sandbox/nodes')return mock.sandbox.nodes();
    if(path==='/api/sandbox/edges')return mock.sandbox.edges();
    if(path==='/api/scenarios')return mock.scenarios.create(body);
    if(path==='/api/network-plans')return mock.networkPlans.create(body);
    const planGet=path.match(/^\/api\/network-plans\/([^/]+)$/);if(planGet)return mock.networkPlans.get(planGet[1]);
    const planConfirm=path.match(/^\/api\/network-plans\/([^/]+)\/confirm$/);if(planConfirm)return mock.networkPlans.confirm(planConfirm[1]);
    const planActivate=path.match(/^\/api\/network-plans\/([^/]+)\/activate$/);if(planActivate)return mock.networkPlans.activate(planActivate[1]);
    const planAi=path.match(/^\/api\/network-plans\/([^/]+)\/ai-edge-candidates$/);if(planAi)return mock.networkPlans.aiEdges(planAi[1],body);
    if(path==='/api/ai/sessions/test')return mock.ai.test(body);
    const scenarioRun=path.match(/^\/api\/scenarios\/([^/]+)\/run$/);if(scenarioRun)return mock.scenarios.run(scenarioRun[1],body);
    const scenarioResults=path.match(/^\/api\/scenarios\/([^/]+)\/results$/);if(scenarioResults)return mock.scenarios.results(scenarioResults[1]);
    const scenarioExplain=path.match(/^\/api\/scenarios\/([^/]+)\/explain$/);if(scenarioExplain)return mock.scenarios.explain(scenarioExplain[1],body);
    return{state:'error',error:{code:'MOCK_ROUTE_NOT_FOUND',message:path}};
  }
  const json=(method,path,body)=>request(path,{method,body:JSON.stringify(body)});
  root.NEXUS_API_CLIENT={
    mode,clientId,request,
    workspace:{get:()=>request('/api/workspace')},
    connections:{test:(input)=>json('POST','/api/connections/test',input),create:(input)=>json('POST','/api/connections',input),tables:(id)=>request('/api/connections/'+encodeURIComponent(id)+'/tables'),profile:(input)=>json('POST','/api/databases/profile',{connection:noSecret(input),credential:input.password,credentialRef:input.credentialRef})},
    sources:{analyze:(id,body={})=>json('POST','/api/sources/'+encodeURIComponent(id)+'/analyze',body),sync:(id,body={})=>json('POST','/api/sources/'+encodeURIComponent(id)+'/sync',body),cancel:(id)=>json('POST','/api/sources/'+encodeURIComponent(id)+'/cancel',{}),metricValues:(id)=>request('/api/sources/'+encodeURIComponent(id)+'/metric-values'),aiMappings:(id,body={})=>json('POST','/api/sources/'+encodeURIComponent(id)+'/ai-mapping-candidates',body),startAiMappingJob:(id)=>json('POST','/api/sources/'+encodeURIComponent(id)+'/ai-mapping-jobs',{})},
    mappings:{confirm:(id,body)=>json('POST','/api/mappings/'+encodeURIComponent(id)+'/confirm',body)},
    sandbox:{nodes:()=>request('/api/sandbox/nodes'),edges:()=>request('/api/sandbox/edges')},
    evidence:{get:(id)=>request('/api/evidence/'+encodeURIComponent(id))},
    networkPlans:{create:(body)=>json('POST','/api/network-plans',body),get:(id)=>request('/api/network-plans/'+encodeURIComponent(id)),confirm:(id,body={})=>json('POST','/api/network-plans/'+encodeURIComponent(id)+'/confirm',body),activate:(id)=>json('POST','/api/network-plans/'+encodeURIComponent(id)+'/activate',{}),aiEdges:(id,body={})=>json('POST','/api/network-plans/'+encodeURIComponent(id)+'/ai-edge-candidates',body)},
    networks:{list:()=>request('/api/networks'),get:(id)=>request('/api/networks/'+encodeURIComponent(id)),delete:(id)=>request('/api/networks/'+encodeURIComponent(id),{method:'DELETE'})},
    ai:{testSession:(body)=>json('POST','/api/ai/sessions/test',body),mappingJob:(id)=>request('/api/ai/mapping-jobs/'+encodeURIComponent(id))},
    scenarios:{create:(body)=>json('POST','/api/scenarios',body),run:(id,body)=>json('POST','/api/scenarios/'+encodeURIComponent(id)+'/run',body),results:(id)=>request('/api/scenarios/'+encodeURIComponent(id)+'/results'),explain:(id,body)=>json('POST','/api/scenarios/'+encodeURIComponent(id)+'/explain',body)},
    profileDatabase:(connection)=>json('POST','/api/databases/profile',{connection:noSecret(connection),credential:connection.password,credentialRef:connection.credentialRef}),
    profileSource:(body)=>json('POST','/api/sources/profile',body),
    buildPackage:(body)=>json('POST','/api/packages/build',body),
    aiTest:(body)=>json('POST','/api/ai/test',body),
    sanitize:noSecret,
  };
})(typeof window==='undefined'?globalThis:window);
