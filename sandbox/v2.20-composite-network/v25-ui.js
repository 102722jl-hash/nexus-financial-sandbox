(function(){
  const bridge=window.NEXUS_V24_BRIDGE;
  const contract=window.NEXUS_V25_CONTRACT;
  const domain=window.NEXUS_V25_DOMAIN;
  const run=window.NEXUS_V25_RUN;
  const el=(id)=>document.getElementById(id);
  function render(){
    const report=contract.validate();
    const incomplete=report.nodes.filter((item)=>item.missing.length).length;
    const missingEvidence=report.evidence.filter((item)=>!item.complete&&item.sourceTier!=='MODEL').length;
    el('v25ContractStatus').textContent=report.valid?'READY':'INCOMPLETE';
    el('v25ContractStatus').className=report.valid?'ready':'warning';
    el('v25NodeStatus').textContent=report.nodes.length+' nodes · '+(incomplete?'缺 '+incomplete:'字段齐全');
    el('v25EvidenceStatus').textContent=missingEvidence+' 个待核验';
    el('v25RunStatus').textContent=run.status+' · '+run.runId;
    el('v25ContractNote').textContent='语义层 '+run.semanticsVersion+' · 领域包 '+domain.schemaVersion+' · 公司适配器 '+run.companyAdapter+' · 数据截止时间 '+run.dataCutoff+'。当前公司结果仅为 MODEL_PROTOTYPE，不得晋级正式研究结果。';
  }
  document.addEventListener('nexus:render',render);
  render();
}());
