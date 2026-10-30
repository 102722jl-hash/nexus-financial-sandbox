(function(){
  const key='nexus-v2.17-active-import';
  let record=null;
  try{record=JSON.parse(localStorage.getItem(key)||'null')}catch(error){record=null}
  const domain=window.NEXUS_REQUESTED_DOMAIN;
  if(!record||record.status!=='ACTIVATED'||record.plan?.detectedDomain!==domain){
    window.NEXUS_V216_RUNTIME_IMPORT={status:'NONE',domainId:domain};
    return;
  }
  const mappings=(record.plan.mappings||[]).filter((row)=>row.scope==='DOMAIN_NODE'&&row.status==='MATCHED');
  const byNode=new Map(mappings.map((row)=>[row.target,row]));
  function apply(nodes){
    (nodes||[]).forEach((node)=>{
      const mapping=byNode.get(node.id);
      if(!mapping)return;
      node.importSnapshot={planId:record.plan.planId,packageId:record.packageId,source:mapping.source,candidateValue:mapping.candidateValue,valueClass:'PENDING_REVIEW',status:'CANDIDATE_ACTIVE'};
      node.displayRoleLabel='导入候选 · '+mapping.source;
    });
  }
  apply(window.SANDBOX_DATA?.nodes);
  apply(window.NEXUS_ACTIVE_PACKAGE?.nodes);
  apply(window.NEXUS_V29_AI_PACKAGE?.nodes);
  window.NEXUS_V216_RUNTIME_IMPORT={status:'CANDIDATE_ACTIVE',domainId:domain,packageId:record.packageId,planId:record.plan.planId,updatedNodeIds:[...byNode.keys()],activatedAt:record.activatedAt,formalReady:false,causalStatus:'ABSTAIN'};
}());
