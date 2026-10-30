(function(){
  const data=window.SANDBOX_DATA;
  const meta=window.NEXUS_V25_DOMAIN;
  const adapter=window.NEXUS_V25_ADAPTER;
  const config=window.SANDBOX_V2_CONFIG;
  const allowedNodeIds=new Set(meta.layers.flatMap((layer)=>layer.nodeTypes));
  const nodes=data.nodes.filter((node)=>allowedNodeIds.has(node.id)).map((node)=>({...node,namespace:'domain.'+meta.id+'.'+node.id}));
  const nodeIds=new Set(nodes.map((node)=>node.id));
  const edges=data.edges.filter((edge)=>nodeIds.has(edge.from)&&nodeIds.has(edge.to)).map((edge,index)=>({...edge,id:'DOMAIN-EDGE-'+String(index+1).padStart(3,'0')}));
  const companies=data.companies.filter((company)=>nodeIds.has(company.id)).map((company)=>{
    const adapted=adapter.adapt(company.id);
    return {id:company.id,name:company.name,ticker:company.ticker,companyNodeId:company.id,requiredOutputs:Object.keys(company.exposures),businessSegments:Object.entries(company.exposures).map(([nodeId,weight])=>({nodeId,weight})),modelFamily:config.companyModels[company.id]?.family||null,outputLevel:adapted.outputLevel,evidenceStatus:adapted.evidenceStatus,dataStatus:adapted.quantificationStatus,adapterVersion:adapted.adapterVersion};
  });
  window.NEXUS_V29_AI_PACKAGE={id:meta.id,name:meta.name,version:'ai-infrastructure-graph-1.0.0',contractVersion:meta.contractVersion,layers:meta.layers.map((layer)=>({id:layer.id,title:layer.title})),nodes,edges,companies,scenarioDictionary:meta.scenarioDictionary,modelFamilies:meta.modelFamilies,evidencePolicy:meta.evidencePolicy,legacyAdapter:{source:'SANDBOX_DATA',status:'TRANSITIONAL'}};
}());
