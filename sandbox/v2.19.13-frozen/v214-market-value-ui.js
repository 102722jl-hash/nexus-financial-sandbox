(function(){
  const bridge=window.NEXUS_V24_BRIDGE;
  const valuation=window.NEXUS_V214_MARKET_VALUATION;
  if(!bridge||!valuation)return;
  const el=(id)=>document.getElementById(id);
  const esc=(value)=>String(value??'').replace(/[&<>"']/g,(char)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const pct=(value,digits=1)=>value==null?'DATA_MISSING':(value>=0?'+':'')+Number(value).toFixed(digits)+'%';
  function money(value,result){
    if(value==null)return'DATA_MISSING';
    if(result.currency==='USD')return'$'+Number(value).toLocaleString('zh-CN',{maximumFractionDigits:1})+'bn';
    if(result.currency==='CNY')return'¥'+Number(value).toLocaleString('zh-CN',{maximumFractionDigits:1})+'bn';
    if(result.currency==='KRW')return'₩'+Number(value/1000).toLocaleString('zh-CN',{maximumFractionDigits:1})+'tn';
    return result.currency+' '+Number(value).toLocaleString('zh-CN',{maximumFractionDigits:1})+'bn';
  }
  function baseCompanies(){return bridge.current()?.base.companies||[];}
  function selectedCompany(){return baseCompanies().find((item)=>item.id===bridge.state.selectedCompany)||baseCompanies()[0];}
  function selectedResult(){const company=selectedCompany();return company?valuation.evaluate(company):null;}
  function valueClass(value){return value<0?'negative':value>0?'positive':'';}
  function renderValuationLedger(){
    const company=selectedCompany(),result=selectedResult();if(!company||!result)return;
    const gate=el('v28CompanyGate');gate.querySelector('span').textContent='情景估值输出等级';gate.querySelector('b').textContent='CANDIDATE_VALUATION · NEEDS_HUMAN_REVIEW';gate.querySelector('small').textContent='已接入当前市值与市场校准估值参数；结果可复算，但行情和财务来源仍待人工交叉核验。';
    el('v213ValuationCompany').textContent=company.name+' · '+company.ticker;
    el('v213ValuationMethod').textContent=result.method.replaceAll('_',' / ');
    el('v213ValuationStatus').textContent=result.status+' · NEEDS_HUMAN_REVIEW';
    el('v213ValuationStatus').className='candidate';
    el('v213CurrentMarketCap').textContent=money(result.currentMarketCap,result);
    el('v213BaselineValue').textContent=money(result.baselineEquityValue,result);
    el('v213ScenarioValue').textContent=money(result.scenarioEquityValue,result);
    el('v213ValueChange').textContent=money(result.valueChangeAmount,result);
    el('v213ValueChange').className=valueClass(result.valueChangeAmount);
    el('v213ValueChangePct').textContent=pct(result.valueChangePct)+' · 相对基准情景';
    el('v213MarketUpside').textContent=pct(result.marketUpsidePct);
    el('v213MarketUpside').className=valueClass(result.marketUpsidePct);
    el('v213Formula').textContent=result.formula;
    el('v213Cutoff').textContent=result.quoteDate;
    const inputs=result.method==='MARKET_CALIBRATED_EV_EBITDA'?
      [['当前股价',result.currency+' '+Number(result.price).toLocaleString('zh-CN')],['报价隐含股数',result.impliedSharesBn.toFixed(3)+'bn'],['基准 EBITDA',money(result.baselineEbitda,result)],['基准 EV/EBITDA',result.method&&result.scenarioMultiple!=null?(result.scenarioMultiple/(1+result.multipleChangePct/100)).toFixed(2)+'x':'--'],['基准净债务',money(result.baselineNetDebt,result)],['基准 FCF',money(result.baselineFcf,result)],['EBITDA 情景变化',pct(result.ebitdaChangePct)],['倍数情景变化',pct(result.multipleChangePct)]]:
      [['当前股价','¥'+Number(result.price).toFixed(2)],['报价隐含股数',result.impliedSharesBn.toFixed(3)+'bn'],['基准净利润',money(result.baselineNetIncome,result)],['基准 P/E',result.baselinePe.toFixed(2)+'x'],['情景净利润',money(result.scenarioNetIncome,result)],['情景 P/E',result.scenarioPe.toFixed(2)+'x'],['净利润情景变化',pct(result.earningsChangePct)],['倍数情景变化',pct(result.multipleChangePct)]];
    el('v213InputGrid').innerHTML=inputs.map(([label,value])=>'<div><span>'+esc(label)+'</span><b>'+esc(value)+'</b><small>CALCULATED_LINEAGE_CANDIDATE</small></div>').join('');
    el('v213Missing').innerHTML='<span>来源状态</span><p>行情：'+esc(result.source.quoteStatus)+'　/　财务：'+esc(result.source.fundamentalStatus)+'　/　正式可用：NO</p>';
    el('v213Boundary').textContent='候选估值可复算：当前市值 '+money(result.currentMarketCap,result)+' → 情景股权价值 '+money(result.scenarioEquityValue,result)+' → 市值变化 '+money(result.valueChangeAmount,result)+' / '+pct(result.valueChangePct)+'。不构成投资建议。';
  }
  function renderRanking(){
    const results=valuation.evaluateAll(baseCompanies()),byId=new Map(baseCompanies().map((item)=>[item.id,item]));
    el('companyRanking').innerHTML=results.map((result,index)=>{const company=byId.get(result.companyId);return'<button class="rank-company '+(result.companyId===bridge.state.selectedCompany?'active':'')+'" data-rank-company="'+result.companyId+'"><span>#'+(index+1)+' '+esc(company.ticker)+'</span><b class="'+valueClass(result.valueChangePct)+'">'+pct(result.valueChangePct)+'</b><small>'+esc(company.name)+' · '+money(result.valueChangeAmount,result)+'</small></button>';}).join('');
    const winner=results[0],loser=results.at(-1),winnerCompany=byId.get(winner.companyId),loserCompany=byId.get(loser.companyId),industry=valuation.industry(baseCompanies());
    el('winnerName').textContent=winnerCompany.name;el('winnerValue').textContent=pct(winner.valueChangePct);
    el('loserName').textContent=loserCompany.name;el('loserValue').textContent=pct(loser.valueChangePct);
    el('v27Winner').textContent=winnerCompany.name+' '+pct(winner.valueChangePct);
    el('v27Loser').textContent=loserCompany.name+' '+pct(loser.valueChangePct);
    el('v27IndustryValue').textContent=industry.index.toFixed(1);
    el('industryRange').textContent=industry.low.toFixed(1)+' – '+industry.high.toFixed(1);
    el('industryBase').textContent='等权情景市值指数 '+industry.index.toFixed(1);
    el('dispersion').textContent=(winner.valueChangePct-loser.valueChangePct).toFixed(1)+' pp';
  }
  function renderBridge(){
    const company=selectedCompany(),result=selectedResult();if(!company||!result)return;
    el('bridgeCompany').textContent=company.name+' · '+company.ticker+' · '+result.method.replaceAll('_',' / ');
    const metric=result.method==='MARKET_CALIBRATED_EV_EBITDA'?['EBITDA 情景变化',pct(result.ebitdaChangePct)]:['净利润情景变化',pct(result.earningsChangePct)];
    const multiple=result.method==='MARKET_CALIBRATED_EV_EBITDA'?['情景 EV/EBITDA',result.scenarioMultiple.toFixed(2)+'x']:['情景 P/E',result.scenarioPe.toFixed(2)+'x'];
    const steps=[['当前市值',money(result.currentMarketCap,result),'MARKET_DATA_CANDIDATE'],['收入模型变化',pct(company.revenue),'经营输入'],metric,['倍数变化',pct(result.multipleChangePct),'估值参数'],multiple,['情景股权价值',money(result.scenarioEquityValue,result),money(result.valueChangeAmount,result)+' / '+pct(result.valueChangePct)]];
    el('bridgeFlow').innerHTML=steps.map((step)=>'<div class="bridge-node"><span>'+esc(step[0])+'</span><b>'+esc(step[1])+'</b><small>'+esc(step[2])+'</small></div>').join('');
  }
  function renderCompanyModel(){
    const result=selectedResult();if(!result)return;
    const steps=result.method==='MARKET_CALIBRATED_EV_EBITDA'?
      [['当前市值',money(result.currentMarketCap,result),'报价候选'],['基准 EBITDA',money(result.baselineEbitda,result),'市场倒推'],['情景 EBITDA',money(result.scenarioEbitda,result),pct(result.ebitdaChangePct)],['情景倍数',result.scenarioMultiple.toFixed(2)+'x',pct(result.multipleChangePct)],['情景净债务',money(result.scenarioNetDebt,result),'FCF 变化进入净债务'],['情景股权价值',money(result.scenarioEquityValue,result),money(result.valueChangeAmount,result)+' / '+pct(result.valueChangePct)]]:
      [['当前市值',money(result.currentMarketCap,result),'2026-08-31'],['基准净利润',money(result.baselineNetIncome,result),'2025 年报候选'],['情景净利润',money(result.scenarioNetIncome,result),pct(result.earningsChangePct)],['基准 P/E',result.baselinePe.toFixed(2)+'x','市场校准'],['情景 P/E',result.scenarioPe.toFixed(2)+'x',pct(result.multipleChangePct)],['情景股权价值',money(result.scenarioEquityValue,result),money(result.valueChangeAmount,result)+' / '+pct(result.valueChangePct)]];
    el('driverTree').innerHTML=steps.map((step)=>'<div class="driver-step"><span>'+esc(step[0])+'</span><strong>'+esc(step[1])+'</strong><small>'+esc(step[2])+'</small></div>').join('');
    const parts=[['经营变化',result.attribution.operations],['估值倍数',result.attribution.multiple],['FCF / 净债务',result.attribution.cashFlow],['市值变化合计',result.valueChangeAmount]],max=Math.max(1,...parts.map((item)=>Math.abs(item[1])));
    el('waterfallBars').innerHTML=parts.map(([label,value])=>{const height=Math.max(2,Math.abs(value)/max*44),bottom=value>=0?50:50-height;return'<div class="waterfall-item"><div class="waterfall-axis"><div class="waterfall-fill '+(value<0?'negative':'')+'" style="height:'+height+'%;bottom:'+bottom+'%"></div><span class="waterfall-value" style="'+(value>=0?'bottom:'+(52+height)+'%':'top:'+(52+height)+'%')+'">'+money(value,result)+'</span></div><b>'+esc(label)+'</b></div>';}).join('');
  }
  function render(){
    // Generated networks own these panels until a reviewed company adapter exists.
    // Do not let a built-in domain valuation overwrite their ABSTAIN/DATA_MISSING state.
    if(bridge.state.networkMode==='standalone')return;
    renderValuationLedger();renderRanking();renderBridge();renderCompanyModel();
  }
  document.addEventListener('nexus:render',render);
  document.getElementById('companySelect').addEventListener('change',()=>setTimeout(render,0));
  document.addEventListener('click',(event)=>{if(event.target.closest('[data-rank-company]'))setTimeout(render,0);});
  render();
  window.NEXUS_V214_MARKET_VALUE_UI={render,money,pct};
}());
