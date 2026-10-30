(function(){
  const data=window.SANDBOX_DATA;
  const config=window.SANDBOX_V2_CONFIG;
  const requiredNodeFields=['id','label','layer','sourceType','sourceId','editable','metricType','valueClass','unit','horizon','baselineValue','baselineUnit','accountingPeriod','dataCutoff'];
  const valueClasses=['REPORTED_ACTUAL','MANAGEMENT_GUIDANCE','CONSENSUS_EXPECTATION','CALIBRATED_PARAMETER','ANALYST_ASSUMPTION','CALCULATED_RESULT'];
  const layerOrder=['macro','demand','route','constraint','chain','company'];
  function nodeContract(node){
    const missing=requiredNodeFields.filter((field)=>node[field]===undefined||node[field]===null||node[field]===''||node[field]==='NOT_SET');
    return {nodeId:node.id,metricName:node.label,metricType:node.metricType,valueClass:node.valueClass,unit:node.unit,currency:node.currency||null,baselineValue:node.baselineValue??null,baselineUnit:node.baselineUnit||null,accountingPeriod:node.accountingPeriod||null,dataCutoff:node.dataCutoff||null,sourceClass:node.sourceType==='fact'?'T1_T2_REQUIRED':node.sourceType==='premise'?'T1_T2_PREMISE':'MODEL',editable:node.editable===true,missing,contractStatus:missing.length?'INCOMPLETE':'READY_FOR_VALUE'};
  }
  function evidenceContract(id,item){
    const source=data.sources[item.sourceId]||data.sources.model;
    const publisher=item.publisher||null,publishedAt=item.publishedAt||null,supportsNodeIds=item.supportsNodeIds||[];
    const complete=Boolean(publisher&&publishedAt&&item.originalQuote&&item.locator&&item.snapshotSha256&&source?.url&&supportsNodeIds.length&&['AS_OF_EVIDENCE','POST_EVENT_VALIDATION'].includes(item.temporalRole));
    return {evidenceId:id,fileName:null,publisher,publishedAt,originalQuote:item.originalQuote||null,locator:item.locator||null,sourceUrl:source?.url||null,supportsNodeIds,reviewStatus:complete?'PENDING_REVIEW':'NEEDS_HUMAN_REVIEW',sourceTier:item.sourceTier||'MODEL',temporalRole:item.temporalRole||'UNVERIFIED',complete};
  }
  function validate(){
    const nodes=data.nodes.map(nodeContract);
    const evidence=Object.entries(config.evidenceRegistry).map(([id,item])=>evidenceContract(id,item));
    const errors=[];
    if(!layerOrder.every((layer)=>data.nodes.some((node)=>node.layer===layer)))errors.push('DOMAIN_LAYERS_INCOMPLETE');
    nodes.forEach((node)=>{if(node.missing.length)errors.push('NODE_CONTRACT_INCOMPLETE:'+node.nodeId)});
    evidence.forEach((item)=>{if(item.sourceTier!=='MODEL'&&!item.complete)errors.push('EVIDENCE_INCOMPLETE:'+item.evidenceId)});
    return {valid:errors.length===0,errors,nodes,evidence,checkedAt:null};
  }
  window.NEXUS_V25_CONTRACT={schemaVersion:'1.0.0',requiredNodeFields,valueClasses,layerOrder,nodeContract,evidenceContract,validate};
}());
