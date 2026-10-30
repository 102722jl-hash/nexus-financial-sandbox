(function(root){
  const nodes=[
    {nodeId:'steelRawCost',layer:'demand',label:'焦煤原料成本',value:null,unit:'%',source:'MOCK_CONFIRMED',status:'CONFIRMED'},
    {nodeId:'blastFurnacePool',layer:'chain',label:'高炉炼钢利润',value:null,unit:'%',source:'MOCK_CONFIRMED',status:'CONFIRMED'},
    {nodeId:'baosteel',layer:'company',label:'宝钢股份',entityCode:'600019.SH',baseline:{REVENUE:317508000000},evidenceIds:['EVD-MOCK-1'],companyModel:'INTEGRATED_STEEL',status:'CONFIRMED',source:'STANDARD_METRIC_VALUES'}
  ];
  const edges=[
    {edgeId:'edge-12',sourceNodeId:'cokingCoalPrice',targetNodeId:'steelRawCost',direction:'positive',weight:.7,lagDays:30,confidence:.82,mechanism:'焦煤价格进入高炉原料成本',evidenceSource:'MOCK_REVIEW',status:'CONFIRMED'},
    {edgeId:'edge-13',sourceNodeId:'steelRawCost',targetNodeId:'blastFurnacePool',direction:'negative',weight:.6,lagDays:45,confidence:.78,mechanism:'原料成本变化进入钢材价差',evidenceSource:'MOCK_REVIEW',status:'CONFIRMED'}
  ];
  let sequence=0,profiledTables=[],registeredNetworks=[];
  const metricValues=[
    {metricValueId:'MV-MOCK-1',metricCode:'REVENUE',metricName:'营业收入',entityCode:'600019.SH',value:317508000000,unit:'CURRENCY',currency:'CNY',reportPeriod:'20251231',announcementDate:'20260430',dataCutoff:'2026-05-08',sourceId:'SOURCE-MOCK',sourceTable:'ashareincome',sourceColumn:'tot_oper_rev',sourceRowKey:'MOCK-ROW-1',valueStatus:'REPORTED_ACTUAL',evidenceId:'EVD-MOCK-1',version:'2026-04-30',opdate:'2026-04-30'}
  ];
  const plan={networkPlanId:'PLAN-MOCK',sourceId:'SOURCE-MOCK',domainId:'coal-steel',status:'PENDING_REVIEW',diff:{addedNodes:[],updatedNodes:[{nodeId:'baosteel',layer:'company',label:'宝钢股份',entityCode:'600019.SH',baseline:{REVENUE:317508000000},evidenceIds:['EVD-MOCK-1'],status:'CANDIDATE',companyModel:'INTEGRATED_STEEL'}],removedNodes:[],sharedNodes:['rates'],unavailableNodes:[],addedEdges:[],removedEdges:[],evidenceGaps:[],companyAdapterGaps:[]}};
  const generatedNodes=[
    {nodeId:'import-snapshot',layer:'macro',label:'导入数据快照',sub:'2026-05-08',source:'SOURCE_SNAPSHOT',status:'CONFIRMED_DATA',baseline:{entityCount:1,metricCount:4},evidenceIds:['EVD-MOCK-1']},
    {nodeId:'metric-revenue',layer:'demand',label:'营业收入',sub:'REVENUE',source:'STANDARD_METRIC_VALUES',status:'CONFIRMED_DATA',baseline:{'600019.SH':317508000000},evidenceIds:['EVD-MOCK-1']},
    {nodeId:'metric-operating-cost',layer:'route',label:'营业成本',sub:'OPERATING_COST',source:'STANDARD_METRIC_VALUES',status:'CONFIRMED_DATA',baseline:{'600019.SH':280000000000},evidenceIds:['EVD-MOCK-2']},
    {nodeId:'metric-total-assets',layer:'constraint',label:'资产总额',sub:'TOTAL_ASSETS',source:'STANDARD_METRIC_VALUES',status:'CONFIRMED_DATA',baseline:{'600019.SH':410000000000},evidenceIds:['EVD-MOCK-3']},
    {nodeId:'metric-net-profit',layer:'chain',label:'归母净利润',sub:'NET_PROFIT',source:'STANDARD_METRIC_VALUES',status:'CONFIRMED_DATA',baseline:{'600019.SH':12000000000},evidenceIds:['EVD-MOCK-4']},
    {nodeId:'entity-600019-sh',layer:'company',label:'宝钢股份',sub:'600019.SH',entityCode:'600019.SH',source:'STANDARD_METRIC_VALUES',status:'EXPOSURE_ONLY',baseline:{REVENUE:317508000000,NET_PROFIT:12000000000},evidenceIds:['EVD-MOCK-1','EVD-MOCK-4']}
  ];
  const generatedEdges=[
    {edgeId:'EDGE-MOCK-SCOPE',sourceNodeId:'import-snapshot',targetNodeId:'metric-revenue',direction:'mixed',weight:0,lagDays:0,confidence:1,mechanism:'该指标来自同一只读数据快照。',evidenceSource:['EVD-MOCK-1'],status:'CONFIRMED_LINEAGE',relationType:'DATA_LINEAGE'},
    {edgeId:'EDGE-MOCK-ACCOUNTING',sourceNodeId:'metric-revenue',targetNodeId:'metric-net-profit',direction:'positive',weight:0,lagDays:0,confidence:.85,mechanism:'收入经成本费用和税项桥接至利润。',evidenceSource:'ACCOUNTING_STRUCTURE_V1.0',status:'CONFIRMED_STRUCTURE',relationType:'ACCOUNTING_STRUCTURE'},
    {edgeId:'EDGE-MOCK-ENTITY',sourceNodeId:'metric-net-profit',targetNodeId:'entity-600019-sh',direction:'mixed',weight:0,lagDays:0,confidence:1,mechanism:'该指标属于当前公司。',evidenceSource:['EVD-MOCK-4'],status:'CONFIRMED_LINEAGE',relationType:'ENTITY_METRIC'}
  ];
  const layerLabels=[{id:'macro',label:'数据范围 / 时间',subtitle:'SOURCE & CUTOFF'},{id:'demand',label:'收入与业务规模',subtitle:'REVENUE & SCALE'},{id:'route',label:'成本与经营投入',subtitle:'COST & OPERATIONS'},{id:'constraint',label:'资产与资本约束',subtitle:'BALANCE SHEET'},{id:'chain',label:'利润与现金流',subtitle:'PROFIT & CASH FLOW'},{id:'company',label:'公司 / 数据实体',subtitle:'ENTITIES'}];
  const generatedPlan={networkPlanId:'PLAN-MOCK-GENERATED',sourceId:'SOURCE-MOCK',domainId:'generated-financial',mode:'CREATE_NEW_NETWORK',networkKind:'FINANCIAL_DISCLOSURE_NETWORK',networkName:'导入财务披露网络',outputLevel:'EXPOSURE_ONLY',causalStatus:'ABSTAIN',status:'PENDING_REVIEW',layerLabels,graph:{nodes:generatedNodes,edges:generatedEdges},diff:{addedNodes:generatedNodes,updatedNodes:[],removedNodes:[{scope:'ACTIVE_DOMAIN_NETWORK'}],sharedNodes:[],unavailableNodes:[],addedEdges:generatedEdges,removedEdges:[],evidenceGaps:['INDUSTRY_CAUSAL_EDGES_MISSING'],companyAdapterGaps:[{entityCode:'600019.SH',status:'EXPOSURE_ONLY'}]}};
  let currentPlan=plan;
  const id=(prefix)=>prefix+'-MOCK-'+(++sequence);
  const result=(data,state='ready')=>Promise.resolve({state,data,requestId:id('REQ')});
  root.NEXUS_API_MOCK={
    workspace:{get:()=>result({status:'EMPTY',source:null,mappings:[],metricValues:[],metricValueTotal:0,plan:null,connection:null})},
    connections:{
      test:(input)=>result({status:'CONNECTION_TESTED',readOnly:true,credentialPersisted:false,connection:{...input,password:undefined,credentialRef:undefined},tables:[{name:'steel_financials',schema:input.schema||'public'},{name:'2026年一季报.财务数据',schema:input.schema||'public'}]}),
      create:(input)=>result({status:'CREATED',connectionId:'CONN-MOCK',sourceId:'SOURCE-MOCK',readOnly:true,credentialPersisted:false}),
      tables:(connectionId)=>result({connectionId,tables:[{name:'steel_financials',schema:'public'},{name:'steel_orders',schema:'public'},{name:'2026年一季报.财务数据',schema:'public'}]}),
    },
    sources:{
      analyze:(sourceId,body={})=>{const requested=body.tables?.length?body.tables:['steel_financials'],database='demo_finance',schema='public',column='营业收入.含税';if(body.reset)profiledTables=[];profiledTables=[...new Set([...profiledTables,...requested])];const mappings=profiledTables.map((table)=>({mappingId:'MAP-MOCK-'+table,sourceField:database+'.'+schema+'.'+table+'.'+column,sourceColumn:database+'.'+schema+'.'+table+'.'+column,sourceLocator:{database,schema,table,column},databaseName:database,schemaName:schema,tableName:table,columnName:column,metricCode:'REVENUE',metricName:'营业收入',status:'PENDING_REVIEW',confidence:.94,reason:'自定义表适配器字段候选',evidence:['SCHEMA_PROFILE'],candidateSource:'RULE'}));return result({sourceId,status:'PROFILED',networkIntent:body.networkIntent||'CREATE_NEW_NETWORK',selectedTables:[...profiledTables],profileProgress:{completed:profiledTables.length,total:body.totalTables||profiledTables.length},tableAdapters:profiledTables.map((table)=>({adapterId:'ADAPTER-MOCK-'+table,databaseName:database,schemaName:schema,tableName:table,qualifiedDisplay:database+'.'+schema+'.'+table,identifierMode:'DRIVER_ESCAPED',sourceFieldMode:'STRUCTURED_LOCATOR',profileStatus:'READY',columnCount:1,syncMode:'MAPPED_POINT_IN_TIME'})),mappings,metricCatalog:[{metricCode:'REVENUE',metricName:'营业收入',metricType:'flow',unit:'CURRENCY'}]})},
      sync:(sourceId)=>result({sourceId,status:'SYNCED',rowsRead:1,acceptedRows:1,rejectedRows:0,rejectionReasons:{},metricValuesCreated:1,cutoffStatus:'PASS',sourceSnapshotId:'SNAP-MOCK',evidenceIds:['EVD-MOCK-1'],formalReady:false}),
      metricValues:(sourceId)=>result({sourceId,status:'READY',total:metricValues.length,metricValues}),
      aiMappings:(sourceId)=>result({sourceId,status:'PENDING_REVIEW',candidates:[{sourceField:'memo',metricCode:'REVENUE',confidence:.42,reason:'仅为Mock候选',evidence:['MOCK'],candidateSource:'AI',status:'PENDING_REVIEW'}]}),
    },
    mappings:{confirm:(mappingId,body)=>result({mappingId,status:body.action==='ignore'?'IGNORED':'CONFIRMED',mapping:{...body,status:body.action==='ignore'?'IGNORED':'CONFIRMED'}})},
    ai:{
      test:()=>result({status:'CONNECTED',modelsVisible:1,chatVerified:true,config:{provider:'ollama',baseUrl:'http://127.0.0.1:11434',model:'mock',timeoutSeconds:30,apiKeyPersisted:false}}),
      startMappingJob:(sourceId)=>result({jobId:'AIJOB-MOCK',sourceId,type:'AI_SEMANTIC_PROFILE',status:'QUEUED',totalFields:1,processedFields:0,totalBatches:1,completedBatches:0,candidates:[],errors:[]}),
      mappingJob:(jobId)=>result({jobId,sourceId:'SOURCE-MOCK',type:'AI_SEMANTIC_PROFILE',status:'SUCCEEDED',totalFields:1,processedFields:1,aiQueuedFields:1,totalBatches:1,completedBatches:1,remainingUnresolved:0,candidates:[{mappingId:'MAP-MOCK-steel_financials',sourceField:'demo_finance.public.steel_financials.营业收入.含税',metricCode:'REVENUE',metricName:'营业收入',metricDefinition:{metricCode:'REVENUE',metricName:'营业收入',metricType:'flow',unit:'CURRENCY'},confidence:.91,reason:'字段名和数值规模符合营业收入',evidence:['SOURCE_SCHEMA','LIMITED_VALUE_PROFILE','AI_SEMANTIC_CANDIDATE'],candidateSource:'AI_SEMANTIC',semanticStatus:'CANDIDATE',sampleSummary:{sampleValues:[317508000000],numericSampleRate:1},suggestedAction:'MAP',status:'PENDING_REVIEW'}],errors:[]}),
    },
    networkPlans:{
      create:(body)=>{currentPlan=body?.mode==='CREATE_NEW_NETWORK'?{...generatedPlan,networkName:body.networkName||generatedPlan.networkName}:{...plan,mode:body?.mode||'EXTEND_EXISTING',updatePolicy:body?.mode==='REPLACE_EXISTING'?'REPLACE_DATA_KEEP_DOMAIN':'ADD_OR_UPDATE'};return result(currentPlan)},
      get:()=>result(currentPlan),
      confirm:()=>{currentPlan={...currentPlan,status:'CONFIRMED'};return result(currentPlan)},
      activate:()=>{currentPlan={...currentPlan,status:'ACTIVE'};if(currentPlan.mode==='CREATE_NEW_NETWORK'&&!registeredNetworks.some((item)=>item.networkId===currentPlan.networkPlanId))registeredNetworks.push({networkId:currentPlan.networkPlanId,networkName:currentPlan.networkName,networkKind:currentPlan.networkKind,outputLevel:currentPlan.outputLevel,nodeCount:generatedNodes.length,edgeCount:generatedEdges.length,deletable:true});return result(currentPlan)},
      aiEdges:()=>result({networkPlanId:plan.networkPlanId,status:'PENDING_REVIEW',candidates:[]}),
    },
    networks:{
      list:()=>result({status:'READY',networks:[...registeredNetworks]}),
      get:(networkId)=>networkId===generatedPlan.networkPlanId?result({networkId,networkPlanId:networkId,networkName:generatedPlan.networkName,networkKind:generatedPlan.networkKind,outputLevel:generatedPlan.outputLevel,layerLabels,nodes:generatedNodes,edges:generatedEdges,metricValues,deletable:true}):result(undefined,'empty'),
      delete:(networkId)=>{registeredNetworks=registeredNetworks.filter((item)=>item.networkId!==networkId);return result({status:'DELETED',networkId})},
    },
    sandbox:{
      nodes:()=>result(currentPlan.mode==='CREATE_NEW_NETWORK'?{networkPlanId:currentPlan.networkPlanId,mode:currentPlan.mode,networkKind:currentPlan.networkKind,networkName:currentPlan.networkName,outputLevel:currentPlan.outputLevel,layerLabels,nodes:generatedNodes}:{networkPlanId:currentPlan.networkPlanId,mode:currentPlan.mode,nodes}),
      edges:()=>result(currentPlan.mode==='CREATE_NEW_NETWORK'?{networkPlanId:currentPlan.networkPlanId,mode:currentPlan.mode,networkKind:currentPlan.networkKind,networkName:currentPlan.networkName,outputLevel:currentPlan.outputLevel,edges:generatedEdges}:{networkPlanId:currentPlan.networkPlanId,mode:currentPlan.mode,edges}),
    },
    scenarios:{
      create:(body)=>result({scenarioId:id('SCENARIO'),status:'CREATED',changes:body.changes||[]}),
      run:(scenarioId,body)=>result({scenarioId,status:'CALCULATED',...calculate(body.changes||[])}),
      results:(scenarioId)=>result({scenarioId,status:'PARTIAL',...calculate([])}),
      explain:(scenarioId)=>result({scenarioId,status:'PARTIAL',explanation:'当前解释为候选文本，需人工核验原始证据',confidence:.45,evidence:['MOCK_REVIEW']}),
    },
  };
  function calculate(changes){
    const change=changes.find((item)=>item.metricCode==='JM_PRICE')?.changePercent||0;
    return {
      affectedNodes:nodes.map((node,index)=>({nodeId:node.nodeId,changePercent:Number((change*[-.7,.42,.18][index]).toFixed(2)),confidence:[.82,.78,.45][index],reason:index===0?'焦煤价格下降降低高炉炼钢原料成本':'影响由已登记候选边传播，等待正式证据'})),
      affectedEdges:change?['edge-12','edge-13']:[],
      summary:change?'焦煤成本变化对高炉炼钢利润形成候选影响':'尚未输入情景变化',
    };
  }
})(typeof window==='undefined'?globalThis:window);
