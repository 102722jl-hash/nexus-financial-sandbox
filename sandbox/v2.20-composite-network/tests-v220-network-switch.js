const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

function deferred(){let resolve;const promise=new Promise((done)=>{resolve=done});return{promise,resolve}}
class Element{
  constructor(id=''){this.id=id;this.value='';this.disabled=false;this.hidden=false;this.textContent='';this.dataset={};this.options=[];this.listeners={};}
  addEventListener(type,listener){this.listeners[type]=listener}
  setAttribute(){}
  querySelector(selector){
    if(selector==='.preset-separator')return this.separator;
    const match=selector.match(/^option\[value="(.+)"\]$/);return match?this.options.find((item)=>item.value===match[1])||null:null;
  }
  querySelectorAll(selector){return selector==='[data-generated-network]'?this.options.filter((item)=>item.dataset.generatedNetwork):[]}
  appendChild(item){item.parent=this;item.remove=()=>{this.options=this.options.filter((option)=>option!==item)};this.options.push(item)}
  insertBefore(){}
  get selectedOptions(){return this.options.filter((item)=>item.value===this.value)}
}

const ids=['domainSelect','deleteNetwork','domainCaseLabel','domainCaseTitle','domainCaseDescription','domainStateTitle','domainStateDetail','networkCanvas','quickPresets'];
const elements=Object.fromEntries(ids.map((id)=>[id,new Element(id)]));
elements.domainSelect.value='ai-infrastructure';elements.quickPresets.separator=new Element('separator');
const networks=[
  {networkId:'PLAN-A1111111',networkName:'同名网络',createdAt:'2026-09-21T01:08:50Z',nodeCount:2,edgeCount:1,deletable:true},
  {networkId:'PLAN-B2222222',networkName:'同名网络',createdAt:'2026-09-21T01:53:17Z',nodeCount:3,edgeCount:2,deletable:true},
  {networkId:'PLAN-FIXED000',networkName:'固定网络',createdAt:'2026-09-20T02:00:00Z',nodeCount:4,edgeCount:3,deletable:false},
];
const pending=new Map(),applied=[],alerts=[];
const api={networks:{
  list:async()=>({state:'ready',data:{networks}}),
  get:(id)=>pending.get(id)?.promise||Promise.resolve({state:'error',error:{message:'missing'}}),
  delete:async()=>({state:'error',error:{message:'不可删除'}}),
}};
const bridge={
  state:{},
  applyStandaloneNetwork:(payload)=>{if(payload.throwApply)throw new Error('apply failed');applied.push(payload.networkPlanId);return{applied:true}},
  restoreStaticNetwork:()=>{bridge.restored=(bridge.restored||0)+1},
  render:()=>{},
};
const location={href:'http://127.0.0.1:4186/?domain=ai-infrastructure&v=2.20.0',get search(){return new URL(this.href).search},assign(url){this.href=String(url)}};
const document={
  body:{dataset:{},classList:{remove(){}}},title:'',
  getElementById:(id)=>elements[id],
  querySelectorAll:()=>[],
  querySelector:()=>null,
  createElement:()=>new Element(),
  addEventListener:()=>{},
};
const window={
  location,history:{replaceState(_state,_title,url){location.href=String(url)}},confirm:()=>true,alert:(message)=>alerts.push(message),
  NEXUS_ACTIVE_RUNTIME:{id:'ai-infrastructure',name:'AI',caseTitle:'AI',caseDescription:'AI',presets:[],stageLabels:[]},
  NEXUS_ACTIVE_PACKAGE:{version:'test',nodes:[],edges:[],layers:[]},NEXUS_V24_BRIDGE:bridge,SANDBOX_ENGINE:{parseScenario:()=>({shocks:[]})},NEXUS_API_CLIENT:api,
};
const context={window,document,URL,URLSearchParams,CSS:{escape:(value)=>value},console,setTimeout,clearTimeout};
vm.runInNewContext(fs.readFileSync('v212-domain-ui.js','utf8'),context,{filename:'v212-domain-ui.js'});

(async()=>{
  await new Promise((resolve)=>setImmediate(resolve));
  const ui=window.NEXUS_V212_DOMAIN_UI,select=elements.domainSelect;
  assert.equal(select.options.length,3);
  assert.notEqual(select.options[0].textContent,select.options[1].textContent);
  assert.ok(select.options[0].textContent.endsWith('2026-09-21 09:08'));
  assert.ok(select.options[1].textContent.endsWith('2026-09-21 09:53'));
  assert.ok(select.options[2].textContent.endsWith('2026-09-20'));
  assert.equal(select.options.some((item)=>/A1111111|B2222222|FIXED000/.test(item.textContent)),false);

  const first=deferred(),second=deferred();pending.set('PLAN-A1111111',first);pending.set('PLAN-B2222222',second);
  select.value='generated:PLAN-A1111111';const firstSwitch=ui.switchDomain({target:select});
  assert.equal(select.disabled,true);
  select.value='generated:PLAN-B2222222';const secondSwitch=ui.switchDomain({target:select});
  second.resolve({state:'ready',data:{networkPlanId:'PLAN-B2222222'}});await secondSwitch;
  first.resolve({state:'ready',data:{networkPlanId:'PLAN-A1111111'}});await firstSwitch;
  assert.deepEqual(applied,['PLAN-B2222222']);
  assert.equal(select.value,'generated:PLAN-B2222222');
  assert.equal(new URL(location.href).searchParams.get('network'),'PLAN-B2222222');

  pending.set('PLAN-A1111111',{promise:Promise.resolve({state:'error',error:{message:'load failed'}})});
  select.value='generated:PLAN-A1111111';await ui.switchDomain({target:select});
  assert.equal(select.value,'generated:PLAN-B2222222');
  assert.deepEqual(applied,['PLAN-B2222222']);

  pending.set('PLAN-FIXED000',{promise:Promise.resolve({state:'ready',data:{networkPlanId:'PLAN-FIXED000'}})});
  select.value='generated:PLAN-FIXED000';await ui.switchDomain({target:select});
  assert.equal(elements.deleteNetwork.disabled,true);

  pending.set('PLAN-A1111111',{promise:Promise.resolve({state:'ready',data:{networkPlanId:'PLAN-A1111111',throwApply:true}})});
  select.value='generated:PLAN-A1111111';await ui.switchDomain({target:select});
  assert.equal(select.value,'generated:PLAN-FIXED000');
  assert.equal(select.disabled,false);
  assert.equal(applied.at(-1),'PLAN-FIXED000');

  select.value='ai-infrastructure';await ui.switchDomain({target:select});
  assert.equal(bridge.restored,2);
  assert.equal(new URL(location.href).searchParams.has('network'),false);
  assert.equal(select.disabled,false);

  const pipeline=fs.readFileSync('v218-pipeline-ui.js','utf8');
  assert.equal(pipeline.includes('PLAN-COALPOWER-V1'),false);
  assert.equal(pipeline.includes('restoreSavedNetwork'),false);
  console.log('V2.20 network switching regression tests: 22/22 passed');
})().catch((error)=>{console.error(error);process.exit(1)});
