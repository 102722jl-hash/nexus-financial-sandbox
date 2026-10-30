(function(){
  const bridge=window.NEXUS_V24_BRIDGE;
  const adapter=window.NEXUS_V25_ADAPTER;
  if(!bridge||!adapter)return;
  const {state,nodeMap}=bridge;
  const runtime=window.NEXUS_ACTIVE_RUNTIME;
  const el=(id)=>document.getElementById(id);
  const fmt=(value,digits=1)=>(Number(value)>=0?'+':'')+Number(value||0).toFixed(digits)+'%';
  const esc=(value)=>String(value??'').replace(/[&<>"']/g,(char)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  let selectedStep=0;
  let lastCompany=null;
  let open=false;
  let autoOpened=false;
  let returnFocus=null;

  function company(){return bridge.current()?.base.companies.find((item)=>item.id===state.selectedCompany)||bridge.current()?.base.companies[0];}
  function generatedEntity(){const node=nodeMap[state.selectedCompany];return node?.layer==='company'?node:null}
  function generatedMetricName(code){return bridge.data.nodes.find((node)=>node.importSnapshot?.metricCodes?.includes(code)&&node.layer!=='company')?.label||code}
  function generatedValue(value){const number=Number(value);return Number.isFinite(number)?number.toLocaleString('zh-CN',{maximumFractionDigits:2}):String(value??'DATA_MISSING')}
  function rangeFor(item){return bridge.current()?.companyRanges.find((entry)=>entry.id===item.id);}
  function round(value){return Math.round(Number(value||0)*1000)/1000;}

  function stepsFor(item){
    const operatingProfit=round(item.revenue+item.margin);
    const parts=item.contributions;
    return [
      {id:'revenue',label:'营业收入',value:item.revenue,className:'MODEL_ASSUMPTION',evidenceId:'MODEL-'+item.modelFamily+'-REVENUE',formula:item.modelLabel+' → 收入模型变化 '+fmt(item.revenue),why:runtime.financialBridge.revenueWhy,invalidation:'产品数量、价格、订单、业务组合或收入确认节奏偏离模型设定。'},
      {id:'operating-profit',label:'营业利润影响代理',value:operatingProfit,className:'CALCULATED_LINEAGE',evidenceId:'CALC-OPERATING-PROFIT-PROXY',formula:'收入变化 '+fmt(item.revenue)+' + 利润率影响 '+fmt(item.margin)+' = '+fmt(operatingProfit),why:'该值用于解释收入与利润率如何合并影响营业利润方向，不是公司披露的营业利润率。',invalidation:'成本结构、固定成本吸收、费用率或会计口径与当前简化桥接不一致。'},
      {id:'fcf',label:'自由现金流',value:item.fcf,className:'CALCULATED_LINEAGE',evidenceId:'CALC-FCF-BRIDGE',formula:runtime.financialBridge.fcfFormula(item,fmt),why:'严格复用当前领域引擎的 FCF 桥接公式；权重仍是分析师假设，尚未由历史报表校准。',invalidation:'折旧、税率、营运资本、资本开支、现金转换率或软限制上限偏离当前设定。'},
      {id:'market-value',label:'情景市值变化',value:window.NEXUS_V214_MARKET_VALUATION.evaluate(item).valueChangePct,className:'CALCULATED_LINEAGE_CANDIDATE',evidenceId:'CALC-SCENARIO-EQUITY-VALUE',formula:(()=>{const result=window.NEXUS_V214_MARKET_VALUATION.evaluate(item);return result.formula+' = '+result.currency+' '+result.scenarioEquityValue+'bn；变化 '+result.currency+' '+result.valueChangeAmount+'bn / '+fmt(result.valueChangePct);})(),why:'经营变化进入市场校准估值模型，输出冲击后股权价值及相对基准市值变化。行情与财务底座仍待人工交叉核验。',invalidation:'行情、财务口径、估值倍数或公司经营响应偏离当前候选输入。'}
    ];
  }

  function render(){
    if(state.networkMode==='standalone')return renderGenerated();
    const item=company();
    if(!item)return;
    const adapted=adapter.adapt(item.id);
    const range=rangeFor(item);
    const steps=stepsFor(item);
    if(lastCompany!==item.id){selectedStep=0;lastCompany=item.id;}
    selectedStep=Math.max(0,Math.min(selectedStep,steps.length-1));
    el('v210Company').textContent=item.name;
    el('v210Ticker').textContent=item.ticker+' · '+item.modelFamily;
    el('v210Gate').textContent='CANDIDATE_VALUATION · NEEDS_HUMAN_REVIEW';
    el('v210Formula').textContent=item.modelLabel;
    el('v210Range').textContent=range?fmt(range.low)+' 至 '+fmt(range.high):'--';
    el('v210Steps').innerHTML=steps.map((step,index)=>'<button class="v210-step '+(index===selectedStep?'active':'')+'" data-v210-step="'+index+'"><i>'+String(index+1).padStart(2,'0')+'</i><span>'+esc(step.label)+'<small>'+esc(step.className)+'</small></span><b class="'+(step.value<0?'negative':'')+'">'+fmt(step.value)+'</b></button>').join('');
    renderDetail(steps[selectedStep]);
  }

  function renderGenerated(){
    const entity=generatedEntity();if(!entity)return setOpen(false);
    const impact=Number(bridge.getRuntimeNetwork().state?.impacts?.[entity.id]||0),entries=Object.entries(entity.importSnapshot?.baseline||{}),steps=entries.slice(0,12).map(([code,value])=>({label:generatedMetricName(code),value,className:'REPORTED_ACTUAL',evidenceId:(entity.importSnapshot?.evidenceIds||[])[0]||'EVIDENCE_MISSING',formula:generatedMetricName(code)+' = '+generatedValue(value),why:'该值来自当前导入快照和已确认字段映射；不是模型生成值。',invalidation:'字段映射、报告期、币种或来源行选择发生变化。'}));
    if(lastCompany!==entity.id){selectedStep=0;lastCompany=entity.id}selectedStep=Math.max(0,Math.min(selectedStep,Math.max(0,steps.length-1)));
    el('v210Company').textContent=entity.label;el('v210Ticker').textContent=entity.sub+' · 导入数据实体';el('v210Gate').textContent=(Math.abs(impact)>.01?'SCENARIO_PATH_ONLY':'EXPOSURE_ONLY')+' · COMPANY MODEL ABSTAIN';el('v210Formula').textContent='已确认字段 → 标准指标值 → 当前实体';el('v210Range').textContent=Math.abs(impact)>.01?'路径变化 '+fmt(impact):steps.length+' 项已载入';
    el('v210Steps').innerHTML=steps.length?steps.map((step,index)=>'<button class="v210-step '+(index===selectedStep?'active':'')+'" data-v210-step="'+index+'"><i>'+String(index+1).padStart(2,'0')+'</i><span>'+esc(step.label)+'<small>'+step.className+'</small></span><b>'+esc(generatedValue(step.value))+'</b></button>').join(''):'<p>当前实体没有已确认指标值。</p>';
    if(steps[selectedStep]){const step=steps[selectedStep];el('v210DetailTitle').textContent=step.label;el('v210DetailValue').textContent=generatedValue(step.value);el('v210DetailValue').className='';el('v210Equation').textContent=step.formula;el('v210EvidenceClass').textContent=step.className;el('v210EvidenceId').textContent=step.evidenceId;el('v210Why').textContent=step.why;el('v210Invalidation').textContent=step.invalidation}
  }

  function renderDetail(step){
    el('v210DetailTitle').textContent=step.label;
    el('v210DetailValue').textContent=fmt(step.value);
    el('v210DetailValue').className=step.value<0?'negative':'';
    el('v210Equation').textContent=step.formula;
    el('v210EvidenceClass').textContent=step.className;
    el('v210EvidenceId').textContent=step.evidenceId;
    el('v210Why').textContent=step.why;
    el('v210Invalidation').textContent=step.invalidation;
  }

  function setOpen(value,reason='manual'){
    const wasOpen=open;
    open=Boolean(value);
    if(open&&!wasOpen)returnFocus=document.activeElement;
    document.body.classList.toggle('v210-drawer-open',open);
    el('v210Drawer').setAttribute('aria-hidden',String(!open));
    el('v210Backdrop').hidden=!open;
    if(open){render();el('v210Drawer').dataset.reason=reason;setTimeout(()=>el('v210Close').focus({preventScroll:true}),0);}
    else if(wasOpen&&returnFocus?.focus){setTimeout(()=>returnFocus.focus({preventScroll:true}),0);returnFocus=null;}
  }
  function openForSelected(reason){setOpen(true,reason);}
  function selectCompanyFromUi(){setTimeout(()=>openForSelected('company-selection'),0);}

  el('v210Close').addEventListener('click',()=>setOpen(false));
  el('v210CloseBottom').addEventListener('click',()=>setOpen(false));
  el('v210Backdrop').addEventListener('click',()=>setOpen(false));
  el('v210Steps').addEventListener('click',(event)=>{const button=event.target.closest('[data-v210-step]');if(!button)return;selectedStep=Number(button.dataset.v210Step);render();});
  el('v210OpenCompanyModel').addEventListener('click',()=>{setOpen(false);document.getElementById('openCompanyModel').click();});
  document.addEventListener('keydown',(event)=>{if(event.key==='Escape'&&open)setOpen(false);});
  document.addEventListener('nexus:render',()=>{if(open)render();});
  document.addEventListener('click',(event)=>{if(event.target.closest('[data-rank-company]'))selectCompanyFromUi();});
  document.getElementById('companySelect').addEventListener('change',selectCompanyFromUi);
  document.getElementById('networkCanvas').addEventListener('pointerup',()=>setTimeout(()=>{if(nodeMap[state.selectedNode]?.layer==='company'){state.selectedCompany=state.selectedNode;openForSelected('network-company')}},0));
  document.addEventListener('nexus:playback-stage',(event)=>{
    const stage=Number(event.detail?.stage);
    if(stage===0)autoOpened=false;
    if(stage===6&&state.playbackActive&&!autoOpened){autoOpened=true;openForSelected('playback-finance');selectedStep=0;render();}
    if(stage===7&&open&&el('v210Drawer').dataset.reason==='playback-finance'){selectedStep=3;render();}
  });
  const params=new URLSearchParams(window.location.search);
  if(params.get('companyDrawer')==='1')setTimeout(()=>openForSelected('url-preview'),300);
  window.NEXUS_V210_FINANCIAL_DRAWER={render,setOpen,openForSelected,stepsFor};
}());
