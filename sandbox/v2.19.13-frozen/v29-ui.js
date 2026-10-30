(function(){
  const bridge=window.NEXUS_V24_BRIDGE;
  const compiler=window.NEXUS_V29_GRAPH_COMPILER;
  const domain=window.NEXUS_ACTIVE_PACKAGE;
  const el=(id)=>document.getElementById(id);
  const labels={macro:'宏观',demand:'需求',route:'路线',constraint:'约束',chain:'产业链',company:'公司'};
  let previous=null;
  let isolated=false;

  function currentShockIds(){return (bridge.state.scenarios[bridge.state.active]?.shocks||[]).map((item)=>item.id);}
  function compileCurrent(){
    const result=compiler.compile(domain,bridge.state.selectedCompany,currentShockIds());
    if(result.status!=='RESOLVED'){
      bridge.state.resolvedGraph=result;
      bridge.state.resolvedNodeIds=new Set();
      bridge.state.resolvedEdgeIds=new Set();
      renderFailure(result);
      return result;
    }
    const change=compiler.diff(previous,result);
    bridge.state.resolvedGraph={status:result.status,domainId:result.domainId,domainVersion:result.domainVersion,companyId:result.companyId,shockIds:result.shockIds,nodeIds:result.nodeIds,edgeIds:result.edgeIds,activeNodeIds:result.activeNodeIds,activeEdgeIds:result.activeEdgeIds,layerCounts:result.layerCounts,missingDependencies:result.missingDependencies,outputLevel:result.outputLevel,evidenceStatus:result.evidenceStatus,pathStatus:result.pathStatus,graphHash:result.graphHash};
    bridge.state.resolvedNodeIds=new Set(result.nodeIds);
    bridge.state.resolvedEdgeIds=new Set(result.edgeIds);
    renderResult(result,change);
    previous=result;
    return result;
  }
  function renderResult(result,change){
    el('v29ResolvedCompany').textContent=result.company.name+' · '+result.company.ticker;
    el('v29ResolvedDomain').textContent=domain.name+' · '+domain.version;
    el('v29GraphSize').textContent=result.nodeIds.length+' / '+result.edgeIds.length;
    el('v29PathStatus').textContent=result.pathStatus;
    el('v29PathStatus').className=result.pathStatus==='CONNECTED'?'connected':'disconnected';
    el('v29GraphDiff').textContent=previous?('+'+change.addedNodes.length+' / -'+change.removedNodes.length):'INITIAL';
    el('v29GraphDiff').title='新增：'+(change.addedNodes.join(', ')||'无')+'；删除：'+(change.removedNodes.join(', ')||'无');
    el('v29GraphHash').textContent=result.graphHash;
    el('v29LayerCounts').innerHTML=compiler.requiredLayers.map((layer)=>'<div><span>'+labels[layer]+'</span><b>'+result.layerCounts[layer]+'</b></div>').join('');
  }
  function renderFailure(result){
    el('v29ResolvedCompany').textContent=bridge.state.selectedCompany;
    el('v29ResolvedDomain').textContent=domain.name;
    el('v29GraphSize').textContent='0 / 0';
    el('v29PathStatus').textContent=result.reason||'ABSTAIN';
    el('v29GraphDiff').textContent='--';
    el('v29GraphHash').textContent='NOT_RESOLVED';
    el('v29LayerCounts').innerHTML='';
  }
  function toggleIsolation(){
    isolated=!isolated;
    bridge.state.focus=isolated?'resolved':'all';
    bridge.state.highlightAll=!isolated;
    el('v29ApplyGraph').classList.toggle('active',isolated);
    el('v29ApplyGraph').textContent=isolated?'显示完整领域':'仅显示解析图';
  }
  document.addEventListener('nexus:render',compileCurrent);
  document.addEventListener('click',(event)=>{if(event.target.closest('[data-rank-company]'))setTimeout(compileCurrent,0);});
  document.getElementById('companySelect').addEventListener('change',()=>setTimeout(compileCurrent,0));
  el('v29ApplyGraph').addEventListener('click',toggleIsolation);
  compileCurrent();
}());
