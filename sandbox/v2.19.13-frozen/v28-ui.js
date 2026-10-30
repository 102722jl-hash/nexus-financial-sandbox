(function(){
  const runtime=window.NEXUS_ACTIVE_RUNTIME,db=runtime.database,adapter=window.NEXUS_V25_ADAPTER,bridge=window.NEXUS_V24_BRIDGE;
  const el=(id)=>document.getElementById(id),esc=(value)=>String(value??'').replace(/[&<>"']/g,(char)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  function renderDatabaseAudit(){
    if(runtime.id==='coal-steel'){
      el('v28DbState').textContent='READ ONLY · DATABASE_CANDIDATE';
      el('v28DbTables').textContent=db.coverage.industries+' 行业 · '+db.coverage.industryCompanies+' 公司';
      el('v28DbCoverage').textContent='5 / 5 · 候选财务底座';
      el('v28DbCutoff').textContent=db.coverage.financialCutoff;
      el('v28DbStatement').textContent=db.companies.shenhua.statementType;
      el('v28TargetList').innerHTML=Object.entries(db.companies).map(([id,item])=>'<div data-domain-company="'+id+'"><span>'+esc(item.name)+' · '+esc(item.industry)+'</span><b>'+esc(item.financialStatus)+'</b><small>'+esc(item.code)+' · '+esc(item.reportPeriod)+' · 营收 '+item.revenueBn.toFixed(1)+'bn · FCF '+item.fcfBn.toFixed(1)+'bn</small></div>').join('')+'<div class="coal-quarantine"><span>隔离数据</span><b>'+db.quarantine.length+' 项</b><small>'+esc(db.quarantine.map((item)=>item.id).join(' / '))+'</small></div>';
      el('v28DbNote').textContent='JM.DCE '+db.scenario.tradeDate+' 收盘 '+db.scenario.baselineClose+' '+db.scenario.unit+'；数据库值尚缺原文、稳定定位与快照哈希。';
    }else{
      el('v28DbState').textContent='READ ONLY · VERIFIED';
      el('v28DbTables').textContent=db.accessibleFinancialTables.length+' 张 · A 股';
      el('v28DbCoverage').textContent=db.targetCoverage.matched+' / '+db.targetCoverage.required+' · DATA_MISSING';
      el('v28DbCutoff').textContent=db.requestedCutoff;
      el('v28DbStatement').textContent=db.queryPolicy.preferredStatementType;
      el('v28TargetList').innerHTML=db.targetCompanies.map((item)=>'<div><span>'+esc(item.name)+'</span><b>'+esc(item.status)+'</b><small>'+esc(item.expectedCodes.join(' / '))+'</small></div>').join('');
      el('v28DbNote').textContent='查询门禁：'+db.queryPolicy.visibleDate+'；'+db.queryPolicy.versionOrder+'；opdate cutoff = required。';
    }
  }
  function renderCompanyGate(){
    if(bridge.state.networkMode==='standalone'){
      const node=bridge.nodeMap[bridge.state.selectedCompany],gate=el('v28CompanyGate');
      gate.querySelector('b').textContent='FACTS ONLY · NO VALUATION MODEL';
      gate.querySelector('small').textContent=(node?.label||'当前导入实体')+' 仅展示归属于该公司的导入候选；日期或证据缺失时不会升级为来源事实。';
      return;
    }
    const company=adapter.adapt(bridge.state.selectedCompany),gate=el('v28CompanyGate');
    gate.querySelector('b').textContent=company.outputLevel+' · '+company.quantificationStatus;
    gate.querySelector('small').textContent=runtime.id==='coal-steel'?'已找到 '+company.name+' 的合并财务候选底座；传播弹性与公司暴露仍为 ANALYST_ASSUMPTION。':'当前 PostgreSQL 财务表未覆盖 '+company.name+'；页面数值仅为 ANALYST_ASSUMPTION 模型演示。';
    const modelBadge=document.querySelector('.model-signature>b');if(modelBadge)modelBadge.textContent='ANALYST_ASSUMPTION · '+company.outputLevel;
    const traceBadge=document.querySelector('.trace-formula small');if(traceBadge)traceBadge.textContent='ANALYST_ASSUMPTION · '+company.quantificationStatus;
  }
  function render(){renderDatabaseAudit();renderCompanyGate();}
  document.addEventListener('nexus:render',render);document.addEventListener('click',(event)=>{if(event.target.closest('[data-rank-company]'))setTimeout(renderCompanyGate,0);});document.getElementById('companySelect').addEventListener('change',()=>setTimeout(renderCompanyGate,0));render();
}());
