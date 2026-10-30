(function () {
  const data=window.SANDBOX_DATA,config=window.SANDBOX_V2_CONFIG,db=window.NEXUS_COAL_DB_SNAPSHOT;
  const nodeMap=Object.fromEntries(data.nodes.map((item)=>[item.id,item]));
  const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));
  const softClamp=(value,limit)=>limit*Math.tanh(value/limit);
  const round=(value)=>Math.round(value*1000)/1000;
  const horizons={3:{label:'3M · 价格发现阶段'},12:{label:'12M · 经营兑现阶段'},36:{label:'36M · 产能调整阶段'}};

  function edgeSet(overrides={}){return config.edgeParameters.map((edge)=>({...edge,...(overrides[edge.id]||{})}));}
  function timeWeight(edge,horizon){
    const elapsed=Number(horizon)-Number(edge.delay||0);if(elapsed<=0)return 0;
    const ramp=Math.max(1,Number(edge.ramp)||1);if(elapsed<ramp)return round(elapsed/ramp);
    const plateauEnd=ramp+Math.max(0,Number(edge.persistence)||0);if(elapsed<=plateauEnd)return 1;
    const excess=elapsed-plateauEnd,decay=Math.max(1,Number(edge.decay)||1),rate=edge.reversible===false?.45:1;
    return round(Math.max(edge.reversible===false?.42:.12,1-excess/decay*rate));
  }
  function normalizeShocks(shocks){return(shocks||[]).filter((item)=>nodeMap[item.id]).map((item)=>({id:item.id,label:item.label||nodeMap[item.id].label,value:clamp(Number(item.value)||0,-80,100)}));}
  function exposure(company,impacts){const parts=Object.entries(company.exposures).map(([id,weight])=>({id,weight,value:round((impacts[id]||0)*weight)})).sort((a,b)=>Math.abs(b.value)-Math.abs(a.value));return{parts,total:parts.reduce((sum,item)=>sum+item.value,0)};}
  function drivers(entries){return entries.map(([id,label,value])=>({id,label,value:round(value)}));}

  function companyResults(impacts,direct,horizon){
    return data.companies.map((company)=>{
      const model=config.companyModels[company.id],base=db.companies[company.id],exp=exposure(company,impacts);
      let modelDrivers=[],revenue=0,margin=0,capex=0,supply=0;
      const realized=impacts.coalRealization||0,volume=impacts.mineVolume||0,rawCost=impacts.steelRawCost||0,orders=impacts.steelOrders||0,utilization=impacts.steelUtilization||0;
      if(model.family==='DIVERSIFIED_MINER'){
        const price=realized*model.priceSensitivity,vol=volume*model.volumeSensitivity,buffer=-price*.22;
        modelDrivers=drivers([['price','煤炭实现售价',price],['volume','煤炭销量',vol],['buffer','电力与运输缓冲',buffer]]);
        revenue=price*.70+vol*.22+buffer*.18;margin=price*model.marginLeverage+vol*.12+buffer*.28;capex=Math.max(0,-price)*model.capexResponse;supply=volume*.05;
      }else if(model.family==='PURE_MINER'){
        const price=realized*model.priceSensitivity,vol=volume*model.volumeSensitivity,unitCost=-Math.max(0,-realized)*.08;
        modelDrivers=drivers([['price','煤炭实现售价',price],['volume','煤炭销量',vol],['unitCost','单位成本刚性',unitCost]]);
        revenue=price*.82+vol*.25;margin=price*model.marginLeverage+unitCost;capex=Math.max(0,-price)*model.capexResponse;supply=volume*.04;
      }else if(model.family==='MIXED_MINER'){
        const price=realized*model.priceSensitivity,vol=volume*model.volumeSensitivity,chem=(impacts.cokingPool||0)*.18;
        modelDrivers=drivers([['price','煤炭实现售价',price],['volume','煤炭销量',vol],['chemical','煤化工组合',chem]]);
        revenue=price*.68+vol*.22+chem*.22;margin=price*model.marginLeverage+chem*.28;capex=Math.max(0,-price)*model.capexResponse+Math.max(0,volume)*.04;supply=volume*.05;
      }else if(model.family==='INTEGRATED_STEEL'){
        const costBenefit=-rawCost*model.costPassThrough,orderEffect=orders*model.orderSensitivity,util=utilization*.18;
        modelDrivers=drivers([['orders','钢材订单',orderEffect],['cost','焦煤成本节省',costBenefit],['utilization','高炉利用率',util]]);
        revenue=orderEffect*.72+util*.18;margin=costBenefit*model.marginLeverage+orderEffect*.18+util*.12;capex=Math.max(0,-orders)*model.capexResponse;supply=costBenefit*.08;
      }else{
        const costBenefit=-rawCost*model.costPassThrough,orderEffect=orders*model.orderSensitivity,mix=(impacts.specialSteelPool||0)*.16;
        modelDrivers=drivers([['orders','特钢订单',orderEffect],['cost','原料成本节省',costBenefit],['mix','产品组合',mix]]);
        revenue=orderEffect*.78+mix*.24;margin=costBenefit*model.marginLeverage+orderEffect*.20+mix*.16;capex=Math.max(0,-orders)*model.capexResponse;supply=costBenefit*.05;
      }
      revenue=softClamp(revenue,48);margin=softClamp(margin,24);capex=softClamp(capex,35);
      const fcf=softClamp(revenue*.32+margin*.78-capex*.38,45);
      const policy=(direct.minePolicy||0)*(model.family.includes('MINER')?.025:-.008);
      const demand=revenue*.30,multiple=softClamp(revenue*.075-(direct.rates||0)*model.multipleDuration*.20,18)*.78;
      const contributions={policy:round(policy),demand:round(demand),supply:round(supply),margin:round(margin*.46),capex:round(-capex*.24),multiple:round(multiple)};
      contributions.revenue=round(contributions.demand+contributions.supply);
      const valuation=round(['policy','demand','supply','margin','capex','multiple'].reduce((sum,key)=>sum+contributions[key],0));
      return {...company,baselineFinancials:base,modelFamily:model.family,modelLabel:model.label,drivers:modelDrivers,revenue:round(revenue),margin:round(margin),capex:round(capex),fcf:round(fcf),multipleChange:round(multiple/.78),valuation,valueIndex:round(100+valuation),exposureParts:exp.parts,contributions};
    });
  }

  function solveVariant(shocks,horizon,rangeKey,overrides){
    const edges=edgeSet(overrides),direct=Object.fromEntries(data.nodes.map((item)=>[item.id,0]));normalizeShocks(shocks).forEach((item)=>{direct[item.id]+=item.value;});
    let impacts={...direct},lineage=Object.fromEntries(data.nodes.map((item)=>[item.id,[]])),edgeStates=[];
    for(let pass=0;pass<8;pass+=1){
      const next={...direct},nextLineage=Object.fromEntries(data.nodes.map((item)=>[item.id,[]])),states=[];
      edges.forEach((edge)=>{const timing=timeWeight(edge,horizon),elasticity=Number(edge[rangeKey]??edge.base),contribution=(impacts[edge.from]||0)*elasticity*timing;states.push({...edge,elasticity,timing,contribution:round(contribution)});if(Math.abs(contribution)<.03)return;next[edge.to]+=contribution;nextLineage[edge.to].push({edgeId:edge.id,from:edge.from,value:round(contribution),confidence:edge.confidence,kind:edge.evidenceClass,note:edge.note,timing,evidenceId:edge.evidenceId});});
      data.interactions.forEach((item)=>{const stage=horizon===3?.35:horizon===36?.88:1,contribution=(impacts[item.a]||0)*(impacts[item.b]||0)*item.coefficient*stage;if(Math.abs(contribution)<.03)return;next[item.target]+=contribution;nextLineage[item.target].push({edgeId:'INTERACTION-'+item.a+'-'+item.b,from:item.a+' × '+item.b,value:round(contribution),confidence:.35,kind:'MODEL_ASSUMPTION',note:item.label,timing:stage,evidenceId:'EV-ANALYST-EDGE',interaction:true});});
      Object.keys(next).forEach((id)=>{next[id]=direct[id]+softClamp(next[id]-direct[id],80);});impacts=next;lineage=nextLineage;edgeStates=states;
    }
    const companies=companyResults(impacts,direct,horizon),constraints=data.nodes.filter((item)=>item.layer==='constraint').map((item)=>({...item,impact:round(impacts[item.id]||0)})).filter((item)=>item.impact<-2).sort((a,b)=>a.impact-b.impact);
    const secondOrder=data.interactions.map((item)=>({...item,value:round((impacts[item.a]||0)*(impacts[item.b]||0)*item.coefficient)})).filter((item)=>Math.abs(item.value)>.25).sort((a,b)=>Math.abs(b.value)-Math.abs(a.value));
    const industryValue=round(100+companies.reduce((sum,item)=>sum+item.valuation,0)/companies.length);
    return{direct,impacts:Object.fromEntries(Object.entries(impacts).map(([id,value])=>[id,round(value)])),lineage,edgeStates,companies,constraints,secondOrder,industryValue,horizon:Number(horizon),horizonLabel:horizons[horizon]?.label||horizons[12].label,insight:buildInsight(companies,direct),path:buildPath(shocks,impacts,edgeStates,companies)};
  }
  function evaluate(shocks,horizon=12,overrides={}){const variants={low:solveVariant(shocks,horizon,'low',overrides),base:solveVariant(shocks,horizon,'base',overrides),high:solveVariant(shocks,horizon,'high',overrides)};const companyRanges=data.companies.map((company)=>{const values=['low','base','high'].map((key)=>variants[key].companies.find((item)=>item.id===company.id)),range=values.map((item)=>item.valuation);return{id:company.id,low:round(Math.min(...range)),base:values[1].valuation,high:round(Math.max(...range)),company:values[1]};});const industry=[variants.low.industryValue,variants.base.industryValue,variants.high.industryValue];return{shocks:normalizeShocks(shocks),horizon:Number(horizon),variants,base:variants.base,companyRanges,industryRange:{low:Math.min(...industry),base:variants.base.industryValue,high:Math.max(...industry)},phaseNotes:buildPhaseNotes(),invalidations:buildInvalidations(shocks,variants.base.edgeStates)};}
  function compare(a,b,horizon=12,overrides={}){const aa=evaluate(a,horizon,overrides),bb=evaluate(b,horizon,overrides),keys=['policy','demand','supply','margin','capex','multiple'];const rows=data.companies.map((company)=>{const av=aa.base.companies.find((item)=>item.id===company.id),bv=bb.base.companies.find((item)=>item.id===company.id),attribution=Object.fromEntries(keys.map((key)=>[key,round(av.contributions[key]-bv.contributions[key])]));return{id:company.id,name:company.name,ticker:company.ticker,a:av.valuation,b:bv.valuation,delta:round(av.valuation-bv.valuation),attribution};}).sort((x,y)=>Math.abs(y.delta)-Math.abs(x.delta));return{a:aa,b:bb,rows,attributionKeys:keys};}
  function sensitivity(shocks,horizon,companyId,overrides={}){const value=(items)=>evaluate(items,horizon,overrides).base.companies.find((item)=>item.id===companyId)?.valuation||0,base=value(shocks);return normalizeShocks(shocks).map((shock)=>{const low=normalizeShocks(shocks).map((item)=>item.id===shock.id?{...item,value:item.value*.7}:item),high=normalizeShocks(shocks).map((item)=>item.id===shock.id?{...item,value:item.value*1.3}:item),lv=value(low)-base,hv=value(high)-base;return{id:shock.id,label:nodeMap[shock.id]?.label||shock.id,low:round(lv),high:round(hv),span:round(Math.abs(hv-lv))};}).sort((a,b)=>b.span-a.span);}
  function buildPhaseNotes(){return{3:'期货价格与现货预期先变化，公司长协、库存和采购周期使报表响应滞后。',12:'实现售价、原料成本、订单与利用率进入经营模型，收入、利润率和 FCF 开始分化。',36:'煤矿供给、钢厂路线和资本开支可能调整，短期成本红利未必持续。'};}
  function buildInvalidations(shocks,states){const active=new Set(normalizeShocks(shocks).map((item)=>item.id)),items=states.filter((edge)=>active.has(edge.from)&&Math.abs(edge.contribution)>.1).map((edge)=>edge.invalidation);return[...new Set(items.concat(['焦煤下跌由钢材需求恶化而非供给宽松驱动','公司长协比例、产品组合或成本结构显著偏离假设','传播参数落在低/高区间之外']))].slice(0,5);}
  function buildInsight(companies,direct){const sorted=[...companies].sort((a,b)=>b.valuation-a.valuation),winner=sorted[0],loser=sorted.at(-1);if((direct.cokingCoalPrice||0)<0)return'焦煤价格下降时，钢企的原料成本边际改善，但煤企实现售价承压；'+winner.name+'相对受益，'+loser.name+'压力最大。若焦煤下跌源于钢材需求走弱，钢企成本利好可能被订单下降抵消。';return winner.name+'在当前条件下相对受益，'+loser.name+'承受较大压力；该排序来自分析假设，不是已识别因果或投资建议。';}
  function buildPath(shocks,impacts,states,companies){const normalized=normalizeShocks(shocks);if(!normalized.length)return[];const main=[...normalized].sort((a,b)=>Math.abs(b.value)-Math.abs(a.value))[0],path=[{id:main.id,value:main.value,note:'用户输入'}],visited=new Set([main.id]);let cursor=main.id;for(let i=0;i<6;i+=1){const next=states.filter((edge)=>edge.from===cursor&&!visited.has(edge.to)).sort((a,b)=>Math.abs(b.contribution)-Math.abs(a.contribution))[0];if(!next||Math.abs(next.contribution)<.03)break;cursor=next.to;visited.add(cursor);path.push({id:cursor,value:impacts[cursor],note:'延迟 '+next.delay+'M / 爬坡 '+next.ramp+'M',confidence:next.confidence,edgeId:next.id});if(nodeMap[cursor]?.layer==='company')break;}if(!path.some((item)=>nodeMap[item.id]?.layer==='company')){const company=[...companies].sort((a,b)=>Math.abs(b.valuation)-Math.abs(a.valuation))[0];path.push({id:company.id,value:company.valuation,note:'公司专属财务桥接'});}return path;}
  function edgeDetails(edgeId,overrides={}){const edge=edgeSet(overrides).find((item)=>item.id===edgeId);return edge?{...edge,evidence:config.evidenceRegistry[edge.evidenceId]||config.evidenceRegistry['EV-ANALYST-EDGE']}:null;}
  window.SANDBOX_V2_ENGINE={evaluate,compare,sensitivity,timeWeight,edgeDetails,edgeSet,horizons,nodeMap,config};
}());
