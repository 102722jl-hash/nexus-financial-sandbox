(async()=>{
  const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),debug='http://127.0.0.1:9224';
  const target=await (await fetch(debug+'/json/new?'+encodeURIComponent('http://127.0.0.1:4180/?api=mock&domain=coal-steel&view=data&v=2.19.2'),{method:'PUT'})).json();
  const ws=new WebSocket(target.webSocketDebuggerUrl),pending=new Map();let sequence=0;
  await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true})});
  ws.addEventListener('message',(event)=>{const message=JSON.parse(event.data);if(message.id&&pending.has(message.id)){const job=pending.get(message.id);pending.delete(message.id);message.error?job.reject(new Error(message.error.message)):job.resolve(message.result)}});
  const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))});
  const evaluate=async(expression)=>{const result=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(result.exceptionDetails)throw new Error(result.exceptionDetails.exception?.description||result.exceptionDetails.text);return result.result.value};
  const waitFor=async(expression,timeout=12000)=>{const started=Date.now();while(Date.now()-started<timeout){if(await evaluate(expression))return;await new Promise((resolve)=>setTimeout(resolve,80))}throw new Error('WAIT_TIMEOUT: '+expression)};
  await send('Runtime.enable');await send('Page.enable');await waitFor("document.readyState==='complete'&&Boolean(window.NEXUS_V218_PIPELINE)");
  const payload={
    sourceId:'SOURCE-CUSTOM-BROWSER',sourceType:'DATABASE',tables:['fr传媒_2022方法1'],
    metricCatalog:[
      {metricCode:'ENTITY_CODE',metricName:'证券代码',metricType:'dimension'},
      {metricCode:'ENTITY_NAME',metricName:'证券简称',metricType:'dimension'},
      {metricCode:'REPORT_PERIOD',metricName:'报告期',metricType:'dimension'},
      {metricCode:'ANNOUNCEMENT_DATE',metricName:'公告日期',metricType:'dimension'},
      {metricCode:'CUSTOM_SCORE',metricName:'得分',metricType:'score',unit:'SCORE',sourceDefined:true}
    ],
    mappings:[
      ['ENTITY_CODE','股票代码','RULE'],['ENTITY_NAME','股票简称','RULE'],['CUSTOM_SCORE','得分','CUSTOM_NUMERIC'],
      ['REPORT_PERIOD','表级报告期','TABLE_ADAPTER'],['ANNOUNCEMENT_DATE','表级数据可见日','TABLE_ADAPTER']
    ].map(([metricCode,columnName,candidateSource],index)=>({
      mappingId:'MAP-CUSTOM-'+index,sourceField:'workspace.workspace.fr传媒_2022方法1.'+columnName,
      sourceLocator:{database:'workspace',schema:'workspace',table:'fr传媒_2022方法1',column:candidateSource==='TABLE_ADAPTER'?null:columnName},
      databaseName:'workspace',schemaName:'workspace',tableName:'fr传媒_2022方法1',columnName,metricCode,
      metricName:metricCode==='CUSTOM_SCORE'?'得分':columnName,status:'PENDING_REVIEW',confidence:.72,
      reason:candidateSource==='CUSTOM_NUMERIC'?'数值列可作为来源自定义指标，需人工确认含义与单位':'待确认',
      candidateSource,suggestedAction:'MAP'
    }))
  };
  await evaluate("window.dispatchEvent(new CustomEvent('nexus:source-analyzed',{detail:"+JSON.stringify(payload)+"}));true");
  const initial=await evaluate("(()=>{const box=document.getElementById('v218Mappings'),first=box.querySelector('.v218-map-row');return{entityFilter:document.getElementById('v218Entities').value,title:first.querySelector('b').textContent,path:first.querySelector('.v219-map-source span').textContent,fullShown:first.textContent.includes('workspace.workspace.fr传媒_2022方法1.股票代码'),overflow:box.scrollWidth-box.clientWidth,progress:document.getElementById('v218MappingProgress').textContent}})()");
  assert.equal(initial.entityFilter,'');assert.equal(initial.title,'股票代码');assert.equal(initial.path,'workspace.workspace.fr传媒_2022方法1');assert.equal(initial.fullShown,false);assert.ok(initial.overflow<=1);assert.ok(initial.progress.includes('1 个自定义指标待确认'));
  await evaluate("document.getElementById('v218ConfirmRules').click();true");await waitFor("document.getElementById('v218MappingProgress').textContent.startsWith('5 / 5')");
  await evaluate("document.getElementById('v218Sync').click();true");await waitFor("document.getElementById('v218ValueCount').textContent!=='0 条'");
  const final=await evaluate("(()=>({progress:document.getElementById('v218MappingProgress').textContent,valueCount:document.getElementById('v218ValueCount').textContent,pipeline:document.getElementById('v218PipelineState').textContent}))()");
  assert.equal(final.progress,'5 / 5 已确认');assert.equal(final.valueCount,'1 条');assert.equal(final.pipeline,'实际数据已标准化');
  await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});await evaluate("document.querySelector('.v218-pipeline').scrollIntoView({block:'start'});true");await new Promise((resolve)=>setTimeout(resolve,200));
  const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false}),file=path.join(__dirname,'runs','v219-custom-mapping-desktop.png');fs.writeFileSync(file,Buffer.from(shot.data,'base64'));assert.ok(fs.statSync(file).size>40000);
  console.log('V2.19 custom mapping browser tests: 12/12 passed '+JSON.stringify({initial,final}));
  ws.close();await fetch(debug+'/json/close/'+target.id);
})().catch((error)=>{console.error(error);process.exitCode=1});
