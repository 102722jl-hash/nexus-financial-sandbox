(async()=>{
  const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),debug='http://127.0.0.1:9224';
  const target=await (await fetch(debug+'/json/new?'+encodeURIComponent('http://127.0.0.1:4180/?api=mock&domain=coal-steel&view=data&v=2.19.3'),{method:'PUT'})).json();
  const ws=new WebSocket(target.webSocketDebuggerUrl),pending=new Map();let sequence=0;
  await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true})});
  ws.addEventListener('message',(event)=>{const message=JSON.parse(event.data);if(message.id&&pending.has(message.id)){const job=pending.get(message.id);pending.delete(message.id);message.error?job.reject(new Error(message.error.message)):job.resolve(message.result)}});
  const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))});
  const evaluate=async(expression)=>{const result=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(result.exceptionDetails)throw new Error(result.exceptionDetails.exception?.description||result.exceptionDetails.text);return result.result.value};
  const waitFor=async(expression,timeout=12000)=>{const started=Date.now();while(Date.now()-started<timeout){if(await evaluate(expression))return;await new Promise((resolve)=>setTimeout(resolve,80))}throw new Error('WAIT_TIMEOUT: '+expression)};
  await send('Runtime.enable');await send('Page.enable');await waitFor("document.readyState==='complete'&&Boolean(window.NEXUS_V218_PIPELINE)");
  const initial=await evaluate("(()=>({mode:document.getElementById('v219NetworkMode').value,note:document.getElementById('v219ModeNote').textContent,entities:document.getElementById('v218Entities').value,legacy:getComputedStyle(document.querySelector('.v216-resolution-grid')).display,scenario:document.getElementById('v218ScenarioControls').hidden,step:[...document.querySelectorAll('.v215-workflow>div')][2].textContent}))()");
  assert.equal(initial.mode,'CREATE_NEW_NETWORK');assert.ok(initial.note.includes('不加载焦煤—钢铁指标目录'));assert.equal(initial.entities,'');assert.equal(initial.legacy,'none');assert.equal(initial.scenario,true);assert.ok(initial.step.includes('网络语义'));
  const modes=[];
  for(const mode of ['EXTEND_EXISTING','REPLACE_EXISTING','CREATE_NEW_NETWORK']){
    modes.push(await evaluate("(()=>{const s=document.getElementById('v219NetworkMode');s.value='"+mode+"';s.dispatchEvent(new Event('change',{bubbles:true}));return{mode:s.value,summary:document.getElementById('v219IntentSummary').textContent,entities:document.getElementById('v218Entities').value,legacy:getComputedStyle(document.querySelector('.v216-resolution-grid')).display,scenario:document.getElementById('v218ScenarioControls').hidden}})()"));
  }
  assert.ok(modes[0].summary.includes('增加到当前网络')&&modes[0].entities.includes('601088.SH')&&modes[0].legacy!=='none'&&!modes[0].scenario);
  assert.ok(modes[1].summary.includes('覆盖当前网络数据')&&modes[1].legacy!=='none'&&!modes[1].scenario);
  assert.ok(modes[2].summary.includes('创建全新网络')&&modes[2].entities===''&&modes[2].legacy==='none'&&modes[2].scenario);
  await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});await evaluate("document.querySelector('.v219-import-intent').scrollIntoView({block:'start'});true");await new Promise((resolve)=>setTimeout(resolve,200));
  const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false}),file=path.join(__dirname,'runs','v219-intent-first-desktop.png');fs.writeFileSync(file,Buffer.from(shot.data,'base64'));assert.ok(fs.statSync(file).size>40000);
  console.log('V2.19 intent-first browser tests: 13/13 passed '+JSON.stringify({initial,modes}));
  ws.close();await fetch(debug+'/json/close/'+target.id);
})().catch((error)=>{console.error(error);process.exitCode=1});
