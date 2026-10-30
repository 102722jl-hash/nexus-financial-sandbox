(function(){
  const requiredLayers=['macro','demand','route','constraint','chain','company'];
  const stable=(value)=>JSON.stringify(value,Object.keys(value).sort());
  function hash(value){
    const text=typeof value==='string'?value:JSON.stringify(value);
    let result=2166136261;
    for(let index=0;index<text.length;index+=1){result^=text.charCodeAt(index);result=Math.imul(result,16777619)}
    return 'RG-'+(result>>>0).toString(16).padStart(8,'0');
  }
  function validateDomain(domain){
    const errors=[];
    if(!domain||!domain.id)errors.push('DOMAIN_ID_MISSING');
    const layers=(domain?.layers||[]).map((item)=>item.id);
    requiredLayers.forEach((layer)=>{if(!layers.includes(layer))errors.push('LAYER_MISSING:'+layer)});
    const nodeIds=new Set();
    (domain?.nodes||[]).forEach((node)=>{
      if(!node.id||!node.layer)errors.push('NODE_CONTRACT_INCOMPLETE:'+(node.id||'UNKNOWN'));
      if(nodeIds.has(node.id))errors.push('NODE_ID_DUPLICATED:'+node.id);
      nodeIds.add(node.id);
    });
    (domain?.edges||[]).forEach((edge,index)=>{
      if(!nodeIds.has(edge.from)||!nodeIds.has(edge.to))errors.push('EDGE_ENDPOINT_MISSING:'+(edge.id||index));
    });
    (domain?.companies||[]).forEach((company)=>{
      if(!nodeIds.has(company.companyNodeId))errors.push('COMPANY_NODE_MISSING:'+company.id);
      (company.requiredOutputs||[]).forEach((id)=>{if(!nodeIds.has(id))errors.push('COMPANY_DEPENDENCY_MISSING:'+company.id+':'+id)});
    });
    return {valid:errors.length===0,errors};
  }
  function adjacency(domain){
    const incoming=new Map(domain.nodes.map((node)=>[node.id,[]]));
    const outgoing=new Map(domain.nodes.map((node)=>[node.id,[]]));
    domain.edges.forEach((edge)=>{incoming.get(edge.to)?.push(edge);outgoing.get(edge.from)?.push(edge)});
    return {incoming,outgoing};
  }
  function walk(startIds,edgeMap,direction){
    const nodes=new Set(startIds),edges=new Set(),queue=[...startIds];
    while(queue.length){
      const current=queue.shift();
      (edgeMap.get(current)||[]).forEach((edge)=>{
        edges.add(edge.id);
        const next=direction==='up'?edge.from:edge.to;
        if(!nodes.has(next)){nodes.add(next);queue.push(next)}
      });
    }
    return {nodes,edges};
  }
  function compile(domain,companyId,shockIds=[]){
    const validation=validateDomain(domain);
    if(!validation.valid)return {status:'ABSTAIN',reason:'DOMAIN_INVALID',validation};
    const company=domain.companies.find((item)=>item.id===companyId);
    if(!company)return {status:'ABSTAIN',reason:'COMPANY_NOT_REGISTERED',companyId,validation};
    const nodeMap=new Map(domain.nodes.map((node)=>[node.id,node]));
    const missingDependencies=(company.requiredOutputs||[]).filter((id)=>!nodeMap.has(id));
    if(missingDependencies.length)return {status:'ABSTAIN',reason:'COMPANY_DEPENDENCY_MISSING',companyId,missingDependencies,validation};
    const graph=adjacency(domain);
    const roots=[company.companyNodeId,...(company.requiredOutputs||[])];
    const upstream=walk(roots,graph.incoming,'up');
    const validShocks=[...new Set(shockIds)].filter((id)=>nodeMap.has(id));
    const downstream=walk(validShocks,graph.outgoing,'down');
    const activeNodes=new Set();
    if(validShocks.length){
      downstream.nodes.forEach((id)=>{if(upstream.nodes.has(id))activeNodes.add(id)});
      validShocks.forEach((id)=>activeNodes.add(id));
      activeNodes.add(company.companyNodeId);
    }else upstream.nodes.forEach((id)=>activeNodes.add(id));
    const resolvedNodes=domain.nodes.filter((node)=>upstream.nodes.has(node.id));
    const resolvedNodeIds=new Set(resolvedNodes.map((node)=>node.id));
    const resolvedEdges=domain.edges.filter((edge)=>resolvedNodeIds.has(edge.from)&&resolvedNodeIds.has(edge.to));
    const activeEdges=resolvedEdges.filter((edge)=>activeNodes.has(edge.from)&&activeNodes.has(edge.to));
    const layerCounts=Object.fromEntries(requiredLayers.map((layer)=>[layer,resolvedNodes.filter((node)=>node.layer===layer).length]));
    const connected=!validShocks.length||activeEdges.some((edge)=>edge.to===company.companyNodeId)||activeNodes.size>2;
    const manifest={domainId:domain.id,domainVersion:domain.version,companyId,companyAdapterVersion:company.adapterVersion,shockIds:validShocks,nodeIds:resolvedNodes.map((node)=>node.id).sort(),edgeIds:resolvedEdges.map((edge)=>edge.id).sort(),activeNodeIds:[...activeNodes].sort(),activeEdgeIds:activeEdges.map((edge)=>edge.id).sort(),layerCounts,missingDependencies,outputLevel:company.outputLevel,evidenceStatus:company.evidenceStatus,pathStatus:connected?'CONNECTED':'DISCONNECTED'};
    return {status:'RESOLVED',...manifest,graphHash:hash(manifest),nodes:resolvedNodes,edges:resolvedEdges,company};
  }
  function diff(before,after){
    const previousNodes=new Set(before?.nodeIds||[]),nextNodes=new Set(after?.nodeIds||[]),previousEdges=new Set(before?.edgeIds||[]),nextEdges=new Set(after?.edgeIds||[]);
    return {addedNodes:[...nextNodes].filter((id)=>!previousNodes.has(id)),removedNodes:[...previousNodes].filter((id)=>!nextNodes.has(id)),addedEdges:[...nextEdges].filter((id)=>!previousEdges.has(id)),removedEdges:[...previousEdges].filter((id)=>!nextEdges.has(id))};
  }
  window.NEXUS_V29_GRAPH_COMPILER={schemaVersion:'resolved-graph-1.0.0',requiredLayers,validateDomain,compile,diff,hash,stable};
}());
