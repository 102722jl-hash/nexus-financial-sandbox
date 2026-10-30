(function () {
  const data=window.SANDBOX_DATA, config=window.SANDBOX_V2_CONFIG;
  const nodeMap=Object.fromEntries(data.nodes.map((item)=>[item.id,item]));
  const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));
  const softClamp=(value,limit)=>limit*Math.tanh(value/limit);
  const round=(value)=>Math.round(value*1000)/1000;
  const horizons={3:{label:'3M · 即时阶段'},12:{label:'12M · 经营阶段'},36:{label:'36M · 结构阶段'}};

  function edgeSet(overrides={}) {
    return config.edgeParameters.map((edge)=>({ ...edge, ...(overrides[edge.id]||{}) }));
  }
  function timeWeight(edge,horizon) {
    const elapsed=Number(horizon)-Number(edge.delay||0);
    if(elapsed<=0)return 0;
    const ramp=Math.max(1,Number(edge.ramp)||1);
    if(elapsed<ramp)return round(elapsed/ramp);
    const plateauEnd=ramp+Math.max(0,Number(edge.persistence)||0);
    if(elapsed<=plateauEnd)return 1;
    const excess=elapsed-plateauEnd, decay=Math.max(1,Number(edge.decay)||1);
    const decayRate=edge.reversible===false?.45:1;
    return round(Math.max(edge.reversible===false?.42:.12,1-excess/decay*decayRate));
  }
  function normalizeShocks(shocks){
    return (shocks||[]).filter((item)=>nodeMap[item.id]).map((item)=>({id:item.id,label:item.label||nodeMap[item.id].label,value:clamp(Number(item.value)||0,-80,100)}));
  }
  function solveVariant(shocks,horizon,rangeKey,overrides) {
    const edges=edgeSet(overrides), direct=Object.fromEntries(data.nodes.map((item)=>[item.id,0]));
    normalizeShocks(shocks).forEach((item)=>{direct[item.id]+=item.value});
    let impacts={...direct}, lineage=Object.fromEntries(data.nodes.map((item)=>[item.id,[]])), edgeStates=[];
    for(let pass=0;pass<8;pass+=1){
      const next={...direct}, nextLineage=Object.fromEntries(data.nodes.map((item)=>[item.id,[]])), states=[];
      edges.forEach((edge)=>{
        const timing=timeWeight(edge,horizon), elasticity=Number(edge[rangeKey] ?? edge.base), contribution=(impacts[edge.from]||0)*elasticity*timing;
        states.push({id:edge.id,from:edge.from,to:edge.to,elasticity,timing,contribution:round(contribution),confidence:Number(edge.confidence),evidenceClass:edge.evidenceClass,evidenceId:edge.evidenceId,invalidation:edge.invalidation,delay:Number(edge.delay),ramp:Number(edge.ramp),persistence:Number(edge.persistence),decay:Number(edge.decay),reversible:Boolean(edge.reversible)});
        if(Math.abs(contribution)<.03)return;
        next[edge.to]+=contribution;
        nextLineage[edge.to].push({edgeId:edge.id,from:edge.from,value:round(contribution),confidence:Number(edge.confidence),kind:edge.evidenceClass,note:edge.note||'边级传播假设',timing,evidenceId:edge.evidenceId});
      });
      data.interactions.forEach((item)=>{
        const stageFactor=horizon===3?.35:horizon===36?.88:1, contribution=(impacts[item.a]||0)*(impacts[item.b]||0)*item.coefficient*stageFactor;
        if(Math.abs(contribution)<.03)return;
        next[item.target]+=contribution;
        nextLineage[item.target].push({edgeId:'INTERACTION-'+item.a+'-'+item.b,from:item.a+' × '+item.b,value:round(contribution),confidence:.48,kind:'MODEL_ASSUMPTION',note:item.label,timing:stageFactor,evidenceId:'EV-MODEL-ASSUMPTION',interaction:true});
      });
      Object.keys(next).forEach((id)=>{
        const propagated=next[id]-direct[id];
        next[id]=direct[id]+softClamp(propagated,90);
      });
      impacts=next;lineage=nextLineage;edgeStates=states;
    }
    const companies=companyResults(impacts,direct,horizon);
    const constraints=data.nodes.filter((item)=>item.layer==='constraint').map((item)=>({...item,impact:round(impacts[item.id]||0)})).filter((item)=>item.impact<-2).sort((a,b)=>a.impact-b.impact);
    const secondOrder=data.interactions.map((item)=>({...item,value:round((impacts[item.a]||0)*(impacts[item.b]||0)*item.coefficient)})).filter((item)=>Math.abs(item.value)>1.5).sort((a,b)=>Math.abs(b.value)-Math.abs(a.value));
    const industryValue=round(100+companies.reduce((sum,item)=>sum+item.valuation,0)/companies.length);
    return {direct,impacts:Object.fromEntries(Object.entries(impacts).map(([id,value])=>[id,round(value)])),lineage,edgeStates,companies,constraints,secondOrder,industryValue,horizon:Number(horizon),horizonLabel:horizons[horizon]?.label||horizons[12].label,insight:buildInsight(companies,constraints,secondOrder,direct),path:buildPath(shocks,impacts,edgeStates,companies)};
  }

  function exposure(company,impacts){
    const parts=Object.entries(company.exposures).map(([id,weight])=>({id,weight,value:round((impacts[id]||0)*weight)})).sort((a,b)=>Math.abs(b.value)-Math.abs(a.value));
    return {parts,total:parts.reduce((sum,item)=>sum+item.value,0)};
  }
  function makeDrivers(entries){return entries.map(([id,label,value])=>({id,label,value:round(value)}));}
  function companyResults(impacts,direct,horizon){
    return data.companies.map((company)=>{
      const model=config.companyModels[company.id], exp=exposure(company,impacts), family=model.family;
      let drivers=[], revenue=0, margin=0, capex=0, supplyContribution=0;
      if(family==='ACCELERATOR'){
        const volume=(impacts.accelerators||0)*.68+(impacts.generalGpu||0)*.16;
        const price=(impacts.trainingDemand||0)*.10-(direct.hbmSupply||0)*.05-(direct.exportControl||0)*.05;
        const attach=(impacts.networkFabric||0)*.16+(impacts.aiSoftware||0)*.08;
        drivers=makeDrivers([['volume','出货量',volume],['price','ASP',price],['attach','系统附加率',attach]]);
        revenue=volume*model.weights.volume+price*model.weights.price+attach*model.weights.attach;
        margin=revenue*model.marginLeverage+price*.22-Math.max(0,direct.exportControl||0)*.055;
        capex=Math.max(0,revenue)*model.capexIntensity;supplyContribution=(impacts.hbmSupply||0)*.018+(impacts.cowosCapacity||0)*.025;
      }else if(family==='MEMORY'){
        const bits=(impacts.generalGpu||0)*.32+(direct.hbmSupply||0)*.28;
        const price=(impacts.generalGpu||0)*.16-(direct.hbmSupply||0)*.24;
        const mix=(impacts.trainingDemand||0)*.14+(impacts.accelerators||0)*.10;
        drivers=makeDrivers([['bits','Bit 出货',bits],['price','价格',price],['mix','HBM 组合',mix]]);
        revenue=bits*model.weights.bits+price*model.weights.price+mix*model.weights.mix;
        margin=revenue*model.marginLeverage+price*.34;
        capex=Math.max(0,direct.hbmSupply||0)*model.capexIntensity;supplyContribution=bits*.10+price*.08;
      }else if(family==='FOUNDRY'){
        const wafer=(direct.waferCapacity||0)*.32+(impacts.generalGpu||0)*.17+(impacts.customAsic||0)*.08;
        const packaging=(direct.cowosCapacity||0)*.36+(impacts.generalGpu||0)*.18+(impacts.customAsic||0)*.14;
        const utilization=(impacts.trainingDemand||0)*.12+(impacts.customAsic||0)*.10;
        drivers=makeDrivers([['wafer','先进晶圆',wafer],['packaging','先进封装',packaging],['utilization','利用率',utilization]]);
        revenue=wafer*model.weights.wafer+packaging*model.weights.packaging+utilization*model.weights.utilization;
        margin=revenue*model.marginLeverage+utilization*.18;
        capex=(Math.max(0,direct.cowosCapacity||0)+Math.max(0,direct.waferCapacity||0))*model.capexIntensity;supplyContribution=(wafer+packaging)*.07;
      }else if(family==='CLOUD'){
        const consumption=(impacts.cloudServices||0)*.54+(impacts.tokenDemand||0)*.13;
        const monetization=(impacts.aiAdoption||0)*.16+(impacts.aiSoftware||0)*.18;
        const depreciation=(direct.aiCapex||0)*(horizon===3?.08:horizon===12?.20:model.depreciationLag);
        drivers=makeDrivers([['consumption','云使用量',consumption],['monetization','AI 变现',monetization],['depreciation','新增折旧',depreciation]]);
        revenue=consumption*model.weights.consumption+monetization*model.weights.monetization;
        margin=revenue*model.marginLeverage-depreciation*.18;
        capex=(direct.aiCapex||0)*model.capexIntensity;supplyContribution=(impacts.powerSupply||0)*.025;
      }else{
        const orders=exp.total*.64+(impacts.dcBuildout||0)*.12;
        const backlog=orders*(horizon===3?.72:horizon===12?.48:.24);
        const capacityId=company.id==='arista'?'networkCapacity':company.id==='eaton'?'transformerCapacity':'coolingCapacity';
        const delivery=(impacts[capacityId]||0)*.32;
        drivers=makeDrivers([['orders','新增订单',orders],['backlog','积压转化',backlog],['delivery','交付能力',delivery]]);
        revenue=orders*model.weights.orders+backlog*model.weights.backlog+delivery*model.weights.delivery;
        margin=revenue*model.marginLeverage+delivery*.10;
        capex=Math.max(0,orders)*model.capexIntensity;supplyContribution=delivery*.12;
      }
      revenue=softClamp(revenue,62);margin=softClamp(margin,28);capex=softClamp(capex,55);
      const fcf=softClamp(revenue*.48+margin*.72-capex*.42,60);
      const policy=-Math.max(0,direct.exportControl||0)*(['nvda','amd'].includes(company.id)?.10:company.id==='avgo'?.025:0);
      const demand=revenue*.2928, supply=supplyContribution;
      const ratePenalty=(direct.rates||0)*model.multipleDuration*.23, growthRerating=clamp(revenue*.10,-5,6);
      const multiple=softClamp(growthRerating-ratePenalty,26)*.82;
      const contributions={policy:round(policy),demand:round(demand),supply:round(supply),margin:round(margin*.4392),capex:round(-capex*.2562),multiple:round(multiple)};
      contributions.revenue=round(contributions.demand+contributions.supply);
      const valuation=round(Object.entries(contributions).filter(([key])=>key!=='revenue').reduce((sum,[,value])=>sum+value,0));
      return {...company,modelFamily:family,modelLabel:model.label,drivers,revenue:round(revenue),margin:round(margin),capex:round(capex),fcf:round(fcf),multipleChange:round(multiple/.82),valuation,valueIndex:round(100+valuation),exposureParts:exp.parts,contributions};
    });
  }

  function evaluate(shocks,horizon=12,overrides={}){
    const variants={low:solveVariant(shocks,horizon,'low',overrides),base:solveVariant(shocks,horizon,'base',overrides),high:solveVariant(shocks,horizon,'high',overrides)};
    const companyRanges=data.companies.map((company)=>{const values=['low','base','high'].map((key)=>variants[key].companies.find((item)=>item.id===company.id)), valuations=values.map((item)=>item.valuation);return{id:company.id,low:round(Math.min(...valuations)),base:values[1].valuation,high:round(Math.max(...valuations)),company:values[1]}});
    const industry=[variants.low.industryValue,variants.base.industryValue,variants.high.industryValue];
    return {shocks:normalizeShocks(shocks),horizon:Number(horizon),variants,base:variants.base,companyRanges,industryRange:{low:Math.min(...industry),base:variants.base.industryValue,high:Math.max(...industry)},phaseNotes:buildPhaseNotes(shocks),invalidations:buildInvalidations(shocks,variants.base.edgeStates)};
  }
  function compare(a,b,horizon=12,overrides={}){
    const resultA=evaluate(a,horizon,overrides),resultB=evaluate(b,horizon,overrides);
    const keys=['policy','demand','supply','margin','capex','multiple'];
    const rows=data.companies.map((company)=>{const av=resultA.base.companies.find((item)=>item.id===company.id),bv=resultB.base.companies.find((item)=>item.id===company.id);const attribution=Object.fromEntries(keys.map((key)=>[key,round(av.contributions[key]-bv.contributions[key])]));return{id:company.id,name:company.name,ticker:company.ticker,a:av.valuation,b:bv.valuation,delta:round(av.valuation-bv.valuation),attribution}}).sort((x,y)=>Math.abs(y.delta)-Math.abs(x.delta));
    return {a:resultA,b:resultB,rows,attributionKeys:keys};
  }
  function sensitivity(shocks,horizon,companyId,overrides={}){
    const base=evaluate(shocks,horizon,overrides).base.companies.find((item)=>item.id===companyId)?.valuation||0;
    return normalizeShocks(shocks).map((shock)=>{const low=normalizeShocks(shocks).map((item)=>item.id===shock.id?{...item,value:item.value*.7}:item),high=normalizeShocks(shocks).map((item)=>item.id===shock.id?{...item,value:item.value*1.3}:item),lowValue=evaluate(low,horizon,overrides).base.companies.find((item)=>item.id===companyId)?.valuation||0,highValue=evaluate(high,horizon,overrides).base.companies.find((item)=>item.id===companyId)?.valuation||0;return{id:shock.id,label:nodeMap[shock.id]?.label||shock.id,low:round(lowValue-base),high:round(highValue-base),span:round(Math.abs(highValue-lowValue))}}).sort((a,b)=>b.span-a.span);
  }
  function buildPhaseNotes(shocks){const ids=new Set((shocks||[]).map((item)=>item.id)),notes={3:'订单、政策风险与瓶颈利用率先变化；尚在延迟期的边不会提前进入报表。',12:'大多数经营链完成爬坡，收入、利润率、CapEx 与 FCF 开始分化。',36:'不可逆扩产仍有残留，短周期需求边按各自持久期与衰减期回落。'};if(ids.has('hbmSupply'))notes[3]='HBM 供给边开始爬坡，Bit 出货改善与价格压力同时进入存储模型。';if(ids.has('aiCapex'))notes[12]='订单和云资本开支进入经营数据，上游收入与云厂商 FCF 可能方向相反。';if(ids.has('inferenceCost'))notes[36]='成本下降的长期结果取决于 Token 需求弹性，Jevons 假设失效时该路径应撤回。';if(ids.has('exportControl'))notes[3]='政策边立即影响可服务市场和风险溢价，收入替代边仍有时间延迟。';return notes;}
  function buildInvalidations(shocks,edgeStates){const active=new Set((shocks||[]).map((item)=>item.id)),list=edgeStates.filter((edge)=>active.has(edge.from)&&Math.abs(edge.contribution)>.1).sort((a,b)=>Math.abs(b.contribution)-Math.abs(a.contribution)).map((edge)=>edge.invalidation);return [...new Set(list.concat(['关键传播弹性落在低/高区间之外','冲击之间出现尚未建模的政策、价格或竞争反馈']))].slice(0,5);}
  function buildInsight(results,constraints,interactions,direct){if(!Object.values(direct).some((value)=>Math.abs(value)>.01))return'系统处于基线。添加冲击后，边级时序、公司专属模型与情景市值会同时重算。';const sorted=[...results].sort((a,b)=>b.valuation-a.valuation),winner=sorted[0],loser=sorted.at(-1);let reason=constraints[0]?'当前最紧约束为'+constraints[0].label+'。':'当前结果主要由需求与财务弹性驱动。';if((direct.aiCapex||0)<0&&results.find((item)=>item.id==='msft')?.fcf>0)reason='上游订单承压，但云厂商削减 CapEx 可阶段性改善 FCF。';else if((direct.hbmSupply||0)>0)reason='Bit 出货改善与价格、扩产压力同时作用，存储公司结果不再按单一供给弹性计算。';else if((direct.inferenceCost||0)<0)reason='Token 需求弹性将价值向网络、电力和云使用量传导，但该路径仍是模型假设。';return winner.name+'在当前参数下相对受益，'+loser.name+'承受最大压力。'+reason+(interactions.length?' 存在显著二阶交叉项。':'');}
  function buildPath(shocks,impacts,edgeStates,companies){const normalized=normalizeShocks(shocks);if(!normalized.length)return[];const main=[...normalized].sort((a,b)=>Math.abs(b.value)-Math.abs(a.value))[0],path=[{id:main.id,value:main.value,note:'用户输入的结构化冲击'}],visited=new Set([main.id]);let current=main.id;for(let step=0;step<6;step+=1){const selected=edgeStates.filter((edge)=>edge.from===current&&!visited.has(edge.to)).sort((a,b)=>Math.abs(b.contribution)-Math.abs(a.contribution))[0];if(!selected||Math.abs(selected.contribution)<.03)break;current=selected.to;visited.add(current);path.push({id:current,value:impacts[current],note:'延迟 '+selected.delay+'M / 爬坡 '+selected.ramp+'M',confidence:selected.confidence,edgeId:selected.id});if(nodeMap[current]?.layer==='company')break;}if(!path.some((item)=>nodeMap[item.id]?.layer==='company')){const company=[...companies].sort((a,b)=>Math.abs(b.valuation)-Math.abs(a.valuation))[0];path.push({id:company.id,value:company.valuation,note:'公司专属财务桥接与情景市值重估'});}return path;}
  function edgeDetails(edgeId,overrides={}){const edge=edgeSet(overrides).find((item)=>item.id===edgeId);if(!edge)return null;return{...edge,evidence:config.evidenceRegistry[edge.evidenceId]||config.evidenceRegistry['EV-MODEL-ASSUMPTION']};}
  window.SANDBOX_V2_ENGINE={evaluate,compare,sensitivity,timeWeight,edgeDetails,edgeSet,horizons,nodeMap,config};
}());
