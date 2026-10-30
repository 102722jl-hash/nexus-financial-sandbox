(function(){
  const data=window.SANDBOX_DATA;
  const domain=window.NEXUS_V25_DOMAIN;
  const config=window.SANDBOX_V2_CONFIG;
  const db=window.NEXUS_V28_DB_SNAPSHOT;
  const outputLevels=Object.fromEntries(data.companies.map((item)=>[item.id,'EXPOSURE_ONLY']));
  function adapt(companyId){
    const company=data.companies.find((item)=>item.id===companyId);
    const model=config.companyModels[companyId];
    if(!company||!model)return {status:'ABSTAIN',companyId,reason:'公司未在当前领域包登记'};
    const candidateFactors=Object.entries(company.exposures).map(([nodeId,weight])=>({nodeId,weight,label:data.nodes.find((node)=>node.id===nodeId)?.label||nodeId}));
    const dbCoverage=db.targetCompanies.find((item)=>item.id===companyId)||{status:'NOT_AUDITED',matches:[]};
    return {companyId,name:company.name,ticker:company.ticker,modelFamily:model.family,modelFormula:model.label,candidateFactors,outputLevel:outputLevels[companyId]||'EXPOSURE_ONLY',evidenceStatus:'NEEDS_HUMAN_REVIEW',quantificationStatus:dbCoverage.status==='DATA_MISSING'?'DATA_MISSING':'MODEL_PROTOTYPE_ONLY',databaseCoverage:dbCoverage.status,databaseMatches:dbCoverage.matches,recommendedInputs:candidateFactors.map((item)=>item.nodeId),adapterVersion:'ai-infrastructure-company-adapter-1.2.0'};
  }
  window.NEXUS_V25_ADAPTER={adapt,adaptAll:()=>data.companies.map((item)=>adapt(item.id)),domainId:domain.id,databaseSnapshot:db.snapshotVersion};
}());
