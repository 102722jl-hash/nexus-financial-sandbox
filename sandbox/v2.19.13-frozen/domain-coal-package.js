(function(){
  const data=window.SANDBOX_DATA;
  const meta=window.NEXUS_V25_DOMAIN;
  const adapter=window.NEXUS_V25_ADAPTER;
  const config=window.SANDBOX_V2_CONFIG;
  const nodes=data.nodes.map((node)=>({...node,namespace:'domain.'+meta.id+'.'+node.id}));
  const edges=data.edges.map((edge,index)=>({...edge,id:'COAL-EDGE-'+String(index+1).padStart(3,'0')}));
  const companies=data.companies.map((company)=>{
    const adapted=adapter.adapt(company.id);
    return {id:company.id,name:company.name,ticker:company.ticker,companyNodeId:company.id,requiredOutputs:Object.keys(company.exposures),businessSegments:Object.entries(company.exposures).map(([nodeId,weight])=>({nodeId,weight})),modelFamily:config.companyModels[company.id]?.family||null,outputLevel:adapted.outputLevel,evidenceStatus:adapted.evidenceStatus,dataStatus:adapted.quantificationStatus,adapterVersion:adapted.adapterVersion};
  });
  window.NEXUS_ACTIVE_PACKAGE={id:meta.id,name:meta.name,version:'coal-steel-graph-1.0.0',contractVersion:meta.contractVersion,layers:meta.layers,nodes,edges,companies,scenarioDictionary:meta.scenarioDictionary,modelFamilies:meta.modelFamilies,evidencePolicy:meta.evidencePolicy};
}());
