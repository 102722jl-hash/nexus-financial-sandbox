(async()=>{
  const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
  const debug=process.env.CHROME_DEBUG||'http://127.0.0.1:9223';
  const pageUrl='http://127.0.0.1:4179/?api=mock&domain=coal-steel&view=data&v=2.18.1';
  const target=await (await fetch(debug+'/json/new?'+encodeURIComponent(pageUrl),{method:'PUT'})).json();
  const ws=new WebSocket(target.webSocketDebuggerUrl),pending=new Map();let sequence=0;
  await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true})});
  ws.addEventListener('message',(event)=>{const message=JSON.parse(event.data);if(message.id&&pending.has(message.id)){const {resolve,reject}=pending.get(message.id);pending.delete(message.id);message.error?reject(new Error(message.error.message)):resolve(message.result)}});
  const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))});
  const evaluate=async(expression)=>{const result=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(result.exceptionDetails)throw new Error(result.exceptionDetails.text);return result.result.value};
  const waitFor=async(expression,timeout=10000)=>{const started=Date.now();while(Date.now()-started<timeout){if(await evaluate(expression))return;await new Promise((resolve)=>setTimeout(resolve,80))}throw new Error('WAIT_TIMEOUT: '+expression)};
  await send('Runtime.enable');await send('Page.enable');await waitFor("document.readyState==='complete'&&Boolean(window.NEXUS_V218_PIPELINE)&&Boolean(window.NEXUS_V24_BRIDGE)");
  await evaluate("window.dispatchEvent(new CustomEvent('nexus:source-analyzed',{detail:{sourceId:'SOURCE-MOCK',mappings:[{mappingId:'MAP-MOCK-1',sourceField:'ashareincome.tot_oper_rev',sourceColumn:'ashareincome.tot_oper_rev',metricCode:'REVENUE',metricName:'营业收入',status:'CONFIRMED',confidence:.94,reason:'测试确认映射',candidateSource:'RULE'}],metricCatalog:[{metricCode:'REVENUE',metricName:'营业收入',metricType:'flow',unit:'CURRENCY'}]}}));true");
  await evaluate("document.getElementById('v218Sync').click();true");await waitFor("document.getElementById('v218CreatePlan').disabled===false");
  await evaluate("document.getElementById('v218CreatePlan').click();true");await waitFor("window.NEXUS_V218_PIPELINE.state.plan?.status==='PENDING_REVIEW'");
  await evaluate("document.getElementById('v218ConfirmPlan').click();true");await waitFor("window.NEXUS_V218_PIPELINE.state.plan?.status==='CONFIRMED'");
  await evaluate("document.getElementById('v218ActivatePlan').click();true");await waitFor("Boolean(window.NEXUS_V24_BRIDGE.state.runtimeNetwork?.networkPlanId)");
  const state=await evaluate("(()=>{const bridge=window.NEXUS_V24_BRIDGE,node=bridge.nodeMap.baosteel;return{view:bridge.state.view,nodeCount:bridge.data.nodes.length,planState:document.getElementById('v218PlanState').textContent,runtime:bridge.state.runtimeNetwork,baosteelImported:node?.importSnapshot?.status,baosteelEvidence:node?.importSnapshot?.evidenceIds||[],duplicate:bridge.data.nodes.some((item)=>item.id==='company-600019-sh'),canvasBytes:document.getElementById('networkCanvas').toDataURL('image/png').length}})()");
  assert.equal(state.view,'world');assert.equal(state.nodeCount,27);assert.equal(state.planState,'已激活并载入主网络');assert.equal(state.baosteelImported,'CONFIRMED');assert.ok(state.baosteelEvidence.includes('EVD-MOCK-1'));assert.equal(state.duplicate,false);assert.ok(state.canvasBytes>5000);assert.deepEqual(state.runtime.updated,['baosteel']);
  const capture=async(name,width,height)=>{
    await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<700});
    await new Promise((resolve)=>setTimeout(resolve,250));
    const result=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
    const file=path.join(__dirname,'runs',name);fs.writeFileSync(file,Buffer.from(result.data,'base64'));assert.ok(fs.statSync(file).size>50000);
  };
  await capture('v218-activated-desktop.png',1440,1000);await capture('v218-activated-mobile.png',390,844);
  console.log('V2.18 browser activation test: 9/9 passed '+JSON.stringify(state));
  ws.close();await fetch(debug+'/json/close/'+target.id);
})().catch((error)=>{console.error(error);process.exitCode=1});
