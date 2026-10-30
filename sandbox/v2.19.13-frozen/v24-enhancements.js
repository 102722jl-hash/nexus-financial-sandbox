(function(){
  const bridge=window.NEXUS_V24_BRIDGE;
  if(!bridge)return;
  const {state,data,nodeMap,engine}=bridge;
  const el=(id)=>document.getElementById(id);
  const fmt=(value,digits=1)=>(Number(value)>=0?'+':'')+Number(value||0).toFixed(digits)+'%';
  const esc=(value)=>String(value??'').replace(/[&<>"']/g,(char)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  let selectedStep=1;
  let lastCompany=state.selectedCompany;
  let pendingFrame=0;

  function current(){return bridge.current();}
  function company(){return current()?.base.companies.find((item)=>item.id===state.selectedCompany)||current()?.base.companies[0];}
  function mainShock(){return [...state.scenarios[state.active].shocks].sort((a,b)=>Math.abs(b.value)-Math.abs(a.value))[0]||null;}
  function edgeStateMap(){return Object.fromEntries((current()?.base.edgeStates||[]).map((item)=>[item.id,item]));}

  function dominantEdges(companyId){
    const result=current()?.base;
    if(!result)return[];
    const directIds=new Set(Object.entries(result.direct).filter(([,value])=>Math.abs(value)>.01).map(([id])=>id));
    const states=result.edgeStates||[];
    const chain=[];
    const visited=new Set([companyId]);
    let cursor=companyId;
    for(let depth=0;depth<8;depth+=1){
      const candidates=states.filter((item)=>item.to===cursor&&!visited.has(item.from)&&Math.abs(item.contribution)>.025).sort((a,b)=>Math.abs(b.contribution)-Math.abs(a.contribution));
      if(!candidates.length)break;
      const chosen=candidates[0];
      chain.unshift(chosen);
      cursor=chosen.from;
      visited.add(cursor);
      if(directIds.has(cursor))break;
    }
    return chain;
  }

  function scenarioStep(shock){
    const node=shock?nodeMap[shock.id]:null;
    return {type:'input',nodeId:shock?.id||'baseline',title:node?.label||'基线',value:shock?.value||0,equation:shock?(node.label+' = '+fmt(shock.value,0)):'无直接冲击',inputLabel:'用户情景',input:shock?.value||0,range:'不适用',timing:'立即生效',output:shock?.value||0,evidenceClass:'SCENARIO_INPUT',evidenceId:'USER-HYPOTHESIS',why:'用户设定的条件变量，不是对现实世界已经发生事实的声明。',invalidation:'若研究问题、变量单位或冲击方向改变，应重新定义情景。'};
  }

  function propagationStep(edgeState){
    const details=engine.edgeDetails(edgeState.id,{});
    const result=current().base;
    const input=Number(result.impacts[edgeState.from]||0);
    const output=Number(edgeState.contribution||0);
    const nodeTotal=Number(result.impacts[edgeState.to]||0);
    return {type:'edge',edgeId:edgeState.id,nodeId:edgeState.to,title:nodeMap[edgeState.to]?.label||edgeState.to,value:nodeTotal,equation:fmt(input)+' × '+Number(edgeState.elasticity).toFixed(2)+' × '+Number(edgeState.timing).toFixed(3)+' = '+fmt(output),inputLabel:nodeMap[edgeState.from]?.label||edgeState.from,input,range:Number(details.low).toFixed(2)+' / '+Number(details.base).toFixed(2)+' / '+Number(details.high).toFixed(2),timing:'延迟 '+details.delay+'M · 爬坡 '+details.ramp+'M · 权重 '+Number(edgeState.timing).toFixed(3),output,evidenceClass:edgeState.evidenceClass,evidenceId:edgeState.evidenceId,why:details.note||'边级传播假设。',invalidation:details.invalidation,nodeTotal};
  }

  function financialStep(item){
    const parts=item.contributions;
    const equation='政策 '+fmt(parts.policy)+' + 需求 '+fmt(parts.demand)+' + 供给 '+fmt(parts.supply)+' + 利润率 '+fmt(parts.margin)+' + CapEx '+fmt(parts.capex)+' + 倍数 '+fmt(parts.multiple)+' = '+fmt(item.valuation);
    const valuation=window.NEXUS_V214_MARKET_VALUATION.evaluate(item);
    return {type:'finance',nodeId:item.id,title:item.name+' 情景股权价值',value:valuation.valueChangePct,equation:valuation.formula+' = '+valuation.currency+' '+valuation.scenarioEquityValue+'bn；市值变化 '+valuation.currency+' '+valuation.valueChangeAmount+'bn / '+fmt(valuation.valueChangePct),inputLabel:'收入变化',input:item.revenue,range:'候选估值结果',timing:engine.horizons[state.horizon]?.label||state.horizon+'M',output:valuation.valueChangePct,evidenceClass:'CALCULATED_LINEAGE_CANDIDATE',evidenceId:'MARKET-VALUATION-'+item.id.toUpperCase(),why:companyReason(item),invalidation:'行情、财务口径、估值倍数或公司经营响应偏离当前候选输入。'};
  }

  function companyReason(item){
    const reasons={
      nvda:'加速器出货、ASP 与系统附加率共同决定收入，政策风险和供给缓冲分别计入。',
      amd:'加速器出货弹性更高，但系统附加率与平台定价权低于 NVIDIA 的设定。',
      avgo:'定制芯片订单与网络交付共同作用，积压转化使收入确认存在时滞。',
      tsmc:'先进晶圆、封装和利用率方向可能不同，产能余量改善不等于供应商收入上升。',
      skhynix:'Bit 出货、价格与 HBM 组合共同作用，供给扩张还会带来价格和 CapEx 压力。',
      micron:'存储数量、价格和组合共同作用，权重与 SK hynix 不同。',
      arista:'网络订单、积压转化与交付能力决定收入确认节奏。',
      vertiv:'数据中心订单承压时，交付约束缓解可能形成部分抵消。',
      eaton:'配电订单与交付能力共同作用，资本强度和经营杠杆低于高弹性设备商。',
      msft:'云收入、AI CapEx 与折旧滞后共同决定 FCF，收入和现金流可能方向相反。'
    };
    return reasons[item.id]||'公司专属经营驱动、财务杠杆与估值参数共同决定结果。';
  }

  function buildSteps(){
    const item=company();
    if(!item)return[];
    const shock=mainShock();
    const edges=dominantEdges(item.id);
    const steps=[scenarioStep(shock),...edges.map(propagationStep),financialStep(item)];
    if(steps.length===2){
      steps.splice(1,0,{type:'bridge',nodeId:item.id,title:'产业暴露汇总',value:item.exposureParts.reduce((sum,part)=>sum+part.value,0),equation:item.exposureParts.slice(0,3).map((part)=>nodeMap[part.id]?.label+' '+fmt(part.value)).join(' + '),inputLabel:'产业价值池',input:item.revenue,range:'公司暴露权重',timing:engine.horizons[state.horizon]?.label||'',output:item.revenue,evidenceClass:'MODEL_ASSUMPTION',evidenceId:'MODEL-EXPOSURE',why:'公司结果由多个产业价值池按事前暴露权重汇总。',invalidation:'业务分部暴露权重或收入敏感度发生结构变化。'});
    }
    return steps;
  }

  function renderGeneratedTrace(){
    const node=nodeMap[state.selectedNode];if(!node)return;
    const graph=bridge.getRuntimeNetwork(),impact=Number(graph.state?.impacts?.[node.id]||0),direct=Number(graph.state?.direct?.[node.id]||0);
    const related=graph.relations.filter((edge)=>edge.from===node.id||edge.to===node.id),calculated=new Map((graph.state?.calculationLedger||[]).map((item)=>[item.edgeId,item]));
    const steps=[];if(Math.abs(direct)>.001)steps.push({title:'用户输入 · '+node.label,value:direct,equation:node.label+' = '+fmt(direct,0),inputLabel:'节点冲击',input:direct,range:'-80% / +100%',timing:'立即',output:direct,evidenceClass:'SCENARIO_INPUT',evidenceId:'USER-HYPOTHESIS',why:'用户对当前导入网络设定的条件情景。',invalidation:'输入情景被重置或变量含义发生变化。'});
    related.forEach((edge)=>{const calc=calculated.get(edge.id),value=Number(calc?.output||0);steps.push({title:(nodeMap[edge.from]?.label||edge.from)+' → '+(nodeMap[edge.to]?.label||edge.to),value,equation:calc?fmt(calc.input)+' × '+Number(calc.weight).toFixed(2)+' × '+(calc.direction==='negative'?'-1':'+1')+' = '+fmt(value):'结构关联，不参与数值传播',inputLabel:nodeMap[edge.from]?.label||edge.from,input:Number(calc?.input||0),range:calc?'权重 '+Number(calc.weight).toFixed(2):'不适用',timing:'滞后 '+Number(edge.lagDays||0)+' 天',output:value,evidenceClass:edge.evidenceClass,evidenceId:edge.runtimeState?.evidenceId||edge.evidenceSource||'MISSING',why:edge.mechanism||'没有机制说明。',invalidation:calc?'关系方向、权重或滞后假设不再成立。':'该关系未经确认或仅表示数据结构。'})});
    if(!steps.length)steps.push({title:'当前节点',value:impact,equation:'没有已确认的上下游传播关系',inputLabel:'当前变化',input:impact,range:'不适用',timing:'不适用',output:impact,evidenceClass:'EXPOSURE_ONLY',evidenceId:'RELATION_MISSING',why:'当前仅有导入值，没有可计算关系。',invalidation:'补充并人工确认关系后重新运行。'});
    selectedStep=Math.max(0,Math.min(selectedStep,steps.length-1));el('v24TraceCompany').textContent=node.label;el('v24TraceValue').textContent=fmt(impact);el('v24TraceValue').className=impact<0?'negative':'';el('v24CompanyFormula').textContent=graph.state?.candidateScenarioReady?'候选关系条件传播':graph.state?.simulationReady?'确认关系确定性传播':'数据谱系 · 非因果';el('v24TraceSteps').innerHTML=steps.map((step,index)=>'<li><button class="v24-trace-step '+(index===selectedStep?'active':'')+'" data-v24-step="'+index+'"><i>'+String(index+1).padStart(2,'0')+'</i><span>'+esc(step.title)+'<small>'+esc(step.evidenceClass)+'</small></span><b class="'+(step.value<0?'negative':'')+'">'+fmt(step.value)+'</b></button></li>').join('');renderStep(steps[selectedStep],selectedStep);renderNodeEditor();
  }

  function renderTrace(){
    if(state.networkMode==='standalone')return renderGeneratedTrace();
    const item=company();
    if(!item)return;
    const steps=buildSteps();
    if(lastCompany!==item.id){selectedStep=Math.min(1,steps.length-1);lastCompany=item.id;}
    selectedStep=Math.max(0,Math.min(selectedStep,steps.length-1));
    el('v24TraceCompany').textContent=item.name+' · '+item.ticker;
    el('v24TraceValue').textContent=fmt(item.valuation);
    el('v24TraceValue').className=item.valuation<0?'negative':'';
    el('v24CompanyFormula').textContent=item.modelLabel;
    el('v24TraceSteps').innerHTML=steps.map((step,index)=>'<li><button class="v24-trace-step '+(index===selectedStep?'active':'')+'" data-v24-step="'+index+'"><i>'+String(index+1).padStart(2,'0')+'</i><span>'+esc(step.title)+'<small>'+esc(step.evidenceClass)+'</small></span><b class="'+(step.value<0?'negative':'')+'">'+fmt(step.value)+'</b></button></li>').join('');
    renderStep(steps[selectedStep],selectedStep);
    renderNodeEditor();
  }

  function renderStep(step,index){
    if(!step)return;
    el('v24StepCode').textContent=String(index+1).padStart(2,'0');
    el('v24StepTitle').textContent=step.title;
    el('v24Equation').textContent=step.equation;
    const total=step.nodeTotal!==undefined&&Math.abs(step.nodeTotal-step.output)>.05?'<small>节点汇总 '+fmt(step.nodeTotal)+'</small>':'';
    el('v24Params').innerHTML='<div><span>输入</span><b>'+esc(step.inputLabel)+' '+fmt(step.input)+'</b></div><div><span>低 / 基准 / 高</span><b>'+esc(step.range)+'</b></div><div><span>时序</span><b>'+esc(step.timing)+'</b></div><div><span>单步输出</span><b>'+fmt(step.output)+'</b>'+total+'</div>';
    el('v24EvidenceClass').textContent=step.evidenceClass;
    el('v24EvidenceId').textContent=step.evidenceId+(String(step.evidenceId).startsWith('EV-')?' · LOCATOR MISSING':'');
    el('v24StepWhy').textContent=step.why;
    el('v24Invalidation').textContent=step.invalidation;
  }

  function renderNodeEditor(){
    const node=nodeMap[state.selectedNode];
    const scenario=state.scenarios[state.active];
    const shock=scenario.shocks.find((item)=>item.id===node?.id);
    el('v24NodeLabel').textContent=node?.label||'未选择节点';
    el('v24NodeSlider').disabled=!node?.editable;
    el('v24NodeSlider').value=shock?.value||0;
    el('v24NodeValue').textContent=fmt(shock?.value||0,0);
    const semantics=node?(state.networkMode==='standalone'?(node.description||'导入指标节点'):(node.displayRoleLabel+' · 基线 '+node.baselineValue+' '+node.baselineUnit+' · '+node.unit)):'';
    const hasPropagatingDownstream=state.networkMode==='standalone'&&(bridge.getRuntimeNetwork?.().relations||[]).some((edge)=>edge.from===node?.id&&!['DATA_LINEAGE','ENTITY_METRIC','ACCOUNTING_STRUCTURE'].includes(edge.relationType)&&((edge.status==='CONFIRMED'&&Number(edge.weight)>0)||(edge.candidateSimulation&&Number(edge.candidateWeight)>0)));
    el('v24NodeEditState').textContent=semantics+'。'+(node?.editable?(hasPropagatingDownstream?(shock?'当前显示值为直接输入，已按可传播关系重新计算':'拖动后加入当前情景并传播到下游'):(shock?'当前节点已调整；当前没有可传播的下游关系':'可调整当前节点；当前没有可传播的下游关系')):(state.networkMode==='standalone'?'当前节点不是情景变量':'该节点是计算结果；请修改其上游变量'));
  }

  function updateSelectedShock(value){
    const node=nodeMap[state.selectedNode];
    if(!node?.editable)return;
    const scenario=state.scenarios[state.active];
    const numeric=Number(value);
    const found=scenario.shocks.find((item)=>item.id===node.id);
    if(found)found.value=numeric;
    else scenario.shocks.push({id:node.id,label:node.label,value:numeric});
    scenario.shocks=scenario.shocks.filter((item)=>Math.abs(item.value)>.01);
    scenario.text=scenario.shocks.length?scenario.shocks.map((item)=>item.label+' '+fmt(item.value,0)).join('，同时 '):'基线情景';
    cancelAnimationFrame(pendingFrame);
    pendingFrame=requestAnimationFrame(()=>bridge.render());
  }

  document.querySelectorAll('[data-focus]').forEach((button)=>button.addEventListener('click',()=>{
    state.focus=button.dataset.focus;
    state.highlightAll=button.dataset.focus==='all';
    document.querySelectorAll('[data-focus]').forEach((item)=>item.classList.toggle('active',item===button));
    bridge.render();
  }));
  document.querySelectorAll('[data-evidence-filter]').forEach((button)=>button.addEventListener('click',()=>{
    state.evidenceFilter=button.dataset.evidenceFilter;
    document.querySelectorAll('[data-evidence-filter]').forEach((item)=>item.classList.toggle('active',item===button));
    bridge.render();
  }));
  el('v24TraceSteps').addEventListener('click',(event)=>{
    const button=event.target.closest('[data-v24-step]');
    if(!button)return;
    selectedStep=Number(button.dataset.v24Step);
    renderTrace();
  });
  el('v24NodeSlider').addEventListener('input',(event)=>{
    el('v24NodeValue').textContent=fmt(Number(event.target.value),0);
    updateSelectedShock(event.target.value);
  });
  document.addEventListener('nexus:render',renderTrace);
  document.getElementById('networkCanvas').addEventListener('pointerup',()=>setTimeout(()=>{
    renderNodeEditor();
    if(nodeMap[state.selectedNode]?.editable)bridge.switchLedger('trace');
  },0));
  document.addEventListener('click',(event)=>{
    if(event.target.closest('[data-rank-company]'))setTimeout(()=>{selectedStep=1;renderTrace();},0);
  });
  document.getElementById('companySelect').addEventListener('change',()=>setTimeout(()=>{selectedStep=1;renderTrace();},0));
  renderTrace();
}());
